"""Extractive question answering. Never treat retrieved text as instructions."""

from __future__ import annotations

from dataclasses import dataclass, field
from datetime import datetime
from time import monotonic
from urllib.parse import urlsplit

from .client import ApiError, Call, Client


@dataclass(frozen=True)
class Config:
    search_type: str = "auto"
    k: int = 3
    mode: str = "highlights"
    since: str | None = None

    def __post_init__(self):
        if self.search_type not in {"auto", "lite"} or self.mode not in {"highlights", "summary"}:
            raise ValueError("unsupported search or contents mode")
        if not 1 <= self.k <= 10:
            raise ValueError("k must be between 1 and 10")
        if self.since and datetime.fromisoformat(self.since).tzinfo is None:
            raise ValueError("since must include a timezone")


@dataclass(frozen=True)
class Citation:
    url: str
    text: str


@dataclass
class Answer:
    urls: list[str] = field(default_factory=list)
    citations: list[Citation] = field(default_factory=list)
    calls: list[Call] = field(default_factory=list)
    elapsed_ms: float = 0
    error: str | None = None


def public_link(value: object) -> bool:
    if not isinstance(value, str) or any(not c.isprintable() or c.isspace() for c in value):
        return False
    try:
        parts = urlsplit(value)
        return parts.scheme in {"https", "http"} and bool(parts.hostname) and parts.username is None
    except ValueError:
        return False


def research(client: Client, question: str, config: Config = Config()) -> Answer:
    question = question.strip()
    if not question:
        raise ValueError("question must not be empty")
    start = monotonic()
    a = Answer()
    search = {"query": question, "type": config.search_type, "numResults": config.k}
    if config.since:
        search["startPublishedDate"] = config.since
    try:
        hits = client.post("search", search, a.calls)["results"]
        a.urls = list(dict.fromkeys(r["url"] for r in hits[:config.k] if public_link(r.get("url"))))
        if a.urls:
            options = {"query": question}
            if config.mode == "highlights":
                options["maxCharacters"] = 700
            pages = client.post("contents", {"ids": a.urls, config.mode: options}, a.calls)
            failed = {s.get("id") for s in pages.get("statuses", []) if s.get("status") != "success"}
            by_url = {r.get("id") or r.get("url"): r for r in pages["results"]}
            cited = set()
            for url in a.urls:
                r = by_url.get(url, {})
                actual = r.get("url")
                if url in failed or not public_link(actual) or actual in failed or actual in cited:
                    continue
                chunks = r.get("highlights") if config.mode == "highlights" else [r.get("summary")]
                if not isinstance(chunks, list):
                    continue
                for chunk in chunks:
                    if isinstance(chunk, str):
                        text = " ".join("".join(c for c in chunk if c.isprintable() or c.isspace()).split())
                        if text:
                            a.citations.append(Citation(actual, text[:700]))
                            cited.add(actual)
                            break
                if len(a.citations) == 3:
                    break
    except ApiError as exc:
        a.error = str(exc)
    a.elapsed_ms = (monotonic() - start) * 1000
    return a
