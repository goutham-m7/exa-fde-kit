"""A single-Webset news inbox; all durable effects are one SQLite transaction."""
from contextlib import closing
from datetime import date, datetime, timezone
import hashlib
import hmac
import html
from http.server import BaseHTTPRequestHandler, HTTPServer
import json
from pathlib import Path
import re
import sqlite3
import time
from urllib.parse import quote, unquote_plus, urlsplit, urlunsplit

from ..agent import public_link


def definition(webset: str, callback: str) -> list[dict]:
    if not webset.strip() or not public_link(callback) or urlsplit(callback).scheme != "https":
        raise ValueError("expected a Webset ID and an HTTPS callback URL")
    base = "https://api.exa.ai/websets/v0"
    return [
        {"method": "POST", "url": base + "/webhooks", "body": {"url": callback, "events": ["webset.item.created"]}},
        {"method": "POST", "url": base + "/monitors", "body": {
            "websetId": webset, "cadence": {"cron": "0 7 * * *", "timezone": "Etc/UTC"},
            "behavior": {"type": "search", "config": {"entity": {"type": "article"}, "count": 5,
                "query": "New funding announcements for AI startups headquartered in India or Singapore",
                "criteria": [{"description": "Reports an announced funding round, not speculation"}],
            }},
        }},
    ]


def verified(body: bytes, header: str, secret: bytes, now: float) -> bool:
    fields = [part.strip().partition("=") for part in header.split(",")]
    stamps = [value for key, _, value in fields if key == "t"]
    if not secret or len(stamps) != 1 or not re.fullmatch(r"[0-9]{1,12}", stamps[0]):
        return False
    if abs(int(now) - int(stamps[0])) > 300:
        return False
    digest = hmac.new(secret, stamps[0].encode() + b"." + body, hashlib.sha256).hexdigest()
    return any(hmac.compare_digest(digest, v.lower()) for k, _, v in fields
               if k == "v1" and re.fullmatch("[a-fA-F0-9]{64}", v))


def canonical(url: str) -> str:
    if not public_link(url) or "\\" in url:
        raise ValueError("invalid article URL")
    u = urlsplit(url)
    host = u.hostname.lower()
    if ":" in host:
        host = f"[{host}]"
    if u.port is not None and u.port != (443 if u.scheme == "https" else 80):
        host += f":{u.port}"
    def relevant(field):
        key = unquote_plus(field.partition("=")[0]).lower()
        return not (key.startswith("utm_") or key in {"gclid", "fbclid"})
    query = "&".join(f for f in u.query.split("&") if relevant(f))
    return urlunsplit((u.scheme, host, u.path or "/", query, ""))


def field(obj: object, key: str) -> str:
    value = obj.get(key) if isinstance(obj, dict) else None
    if not isinstance(value, str) or not value.strip():
        raise ValueError(f"invalid {key}")
    return value


class Inbox:
    def __init__(self, path: Path, webset: str):
        if not webset.strip():
            raise ValueError("a Webset ID is required")
        self.path, self.webset = path, webset
        path.touch(mode=0o600, exist_ok=True)
        with closing(sqlite3.connect(path)) as db, db:
            db.executescript("""
                CREATE TABLE IF NOT EXISTS seen (
                    webset TEXT, kind TEXT, value TEXT, PRIMARY KEY(webset,kind,value));
                CREATE TABLE IF NOT EXISTS articles (
                    webset TEXT, day TEXT, url TEXT, title TEXT, PRIMARY KEY(webset,day,url));
            """)

    def ingest(self, raw: bytes) -> str:
        event = json.loads(raw)
        if field(event, "type") != "webset.item.created":
            return "ignored"
        item = event.get("data")
        if field(item, "websetId") != self.webset:
            return "ignored"
        props = item.get("properties")
        if field(props, "type") != "article":
            return "ignored"
        url = canonical(field(props, "url"))
        created = datetime.fromisoformat(field(event, "createdAt"))
        if created.tzinfo is None:
            raise ValueError("createdAt requires timezone")
        day = created.astimezone(timezone.utc).date().isoformat()
        article = props.get("article")
        if not isinstance(article, dict):
            raise ValueError("missing article")
        title = article.get("title") or props.get("description") or "Untitled article"
        if not isinstance(title, str):
            raise ValueError("invalid title")
        with closing(sqlite3.connect(self.path)) as db, db:
            def first(kind, value):
                return db.execute("INSERT OR IGNORE INTO seen VALUES(?,?,?)", (self.webset, kind, value)).rowcount == 1
            if not first("event", field(event, "id")):
                return "duplicate"
            new_id = first("id", field(item, "id"))
            new_url = first("url", url)
            if not new_id or not new_url:
                return "duplicate"
            db.execute("INSERT INTO articles VALUES(?,?,?,?)", (self.webset, day, url, title))
        return "added"

    def digest(self, day: date) -> str:
        lines = [f"# Funding news · {day} UTC", ""]
        with closing(sqlite3.connect(self.path)) as db:
            for url, title in db.execute("SELECT url,title FROM articles WHERE webset=? AND day=? ORDER BY url",
                                         (self.webset, day.isoformat())):
                text = html.escape(" ".join(title.split()))
                text = re.sub(r"([\\\[\]*_])", r"\\\1", text)
                target = quote(url, safe="%:/?&=+#,;@!$'()*~-._")
                lines.append(f"- {text} — <{target}>")
        if len(lines) == 2:
            lines.append("No new articles.")
        return "\n".join(lines) + "\n"


def receiver(inbox: Inbox, secret: bytes, port: int) -> HTTPServer:
    if not secret:
        raise ValueError("webhook signing secret required")

    class Handler(BaseHTTPRequestHandler):
        timeout = 5

        def log_message(self, *args):
            pass  # No raw request paths, payloads or headers in logs.

        def do_POST(self):
            if self.path != "/webhook":
                return self.send_error(404)
            lengths = self.headers.get_all("Content-Length", [])
            if self.headers.get("Transfer-Encoding") or len(lengths) != 1 or not re.fullmatch("[0-9]{1,10}", lengths[0]):
                return self.send_error(400)
            size = int(lengths[0])
            if size > 1024 * 1024:
                return self.send_error(413)
            raw = self.rfile.read(size)
            signatures = self.headers.get_all("Exa-Signature", [])
            if len(signatures) != 1 or not verified(raw, signatures[0], secret, time.time()):
                return self.send_error(401)
            try:
                status = inbox.ingest(raw)
            except (ValueError, OverflowError, RecursionError):
                return self.send_error(400)
            except sqlite3.Error:
                return self.send_error(503)
            body = json.dumps({"status": status}).encode()
            self.send_response(200)
            self.send_header("Content-Type", "application/json")
            self.send_header("Content-Length", str(len(body)))
            self.end_headers()
            self.wfile.write(body)

    return HTTPServer(("127.0.0.1", port), Handler)
