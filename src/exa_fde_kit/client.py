"""Small, read-only Exa transport. Logs never contain request or response bodies."""

from __future__ import annotations

import hashlib
import json
import logging
import math
import random
import sqlite3
import threading
import time
from contextlib import closing
from dataclasses import asdict, dataclass
from datetime import datetime, timezone
from email.utils import parsedate_to_datetime
from pathlib import Path
from typing import Callable

import httpx

LOG = logging.getLogger("exa_fde_kit")


class ApiError(Exception):
    """Public diagnostic safe to display without leaking queries or credentials."""


@dataclass(frozen=True)
class Call:
    endpoint: str
    attempt: int
    status: int | str
    latency_ms: float
    usd: float | None
    cost_basis: str
    cached: bool = False


class Cache:
    """One SQLite file per operator. Values expire after one hour."""

    def __init__(self, directory: Path):
        directory.mkdir(mode=0o700, parents=True, exist_ok=True)
        self.path = directory / "responses.sqlite3"
        self.path.touch(mode=0o600, exist_ok=True)
        with closing(sqlite3.connect(self.path)) as db, db:
            db.execute("CREATE TABLE IF NOT EXISTS responses (k TEXT PRIMARY KEY, expires REAL, body TEXT)")
            db.execute("DELETE FROM responses WHERE expires <= ?", (time.time(),))

    def get(self, key: str) -> dict | None:
        with closing(sqlite3.connect(self.path)) as db:
            row = db.execute("SELECT body FROM responses WHERE k=? AND expires>?", (key, time.time())).fetchone()
        return json.loads(row[0]) if row else None

    def put(self, key: str, data: dict) -> None:
        with closing(sqlite3.connect(self.path)) as db, db:
            db.execute("INSERT OR REPLACE INTO responses VALUES (?, ?, ?)",
                       (key, time.time() + 3600, json.dumps(data)))


def retry_floor(header: str | None) -> float:
    if not header:
        return 0.0
    if header.strip().isascii() and header.strip().isdigit():
        return float(header)
    try:
        when = parsedate_to_datetime(header)
        return max(0.0, (when - datetime.now(timezone.utc)).total_seconds())
    except (ValueError, TypeError, OverflowError):
        return 0.0


def cost(endpoint: str, body: dict, data: dict) -> tuple[float, str]:
    # PAYG snapshot and limits of this estimate: see README, "Reading the report".
    info = data.get("costDollars")
    total = info.get("total") if isinstance(info, dict) else None
    if type(total) in (int, float) and math.isfinite(total) and total >= 0:
        return total, "response"
    if endpoint == "search":
        return (0.004 if body["type"] == "lite" else 0.007), "list_estimate"
    # One content type per URL; conservatively estimate using all requested IDs.
    return len(body["ids"]) * 0.001, "list_estimate"


class Client:
    def __init__(self, http: httpx.Client, *, concurrency: int = 4,
                 cache_dir: Path | None = None, mode: str = "live",
                 sleep: Callable[[float], None] = time.sleep):
        if concurrency < 1:
            raise ValueError("concurrency must be positive")
        self.http = http
        self.semaphore = threading.BoundedSemaphore(concurrency)
        self.cache = Cache(cache_dir) if cache_dir else None
        self.sleep = sleep
        self.mode = mode
        # Separate live keys and fixtures, including for library callers sharing a cache.
        self.namespace = hashlib.sha256((mode + ":" + http.headers.get("x-api-key", "")).encode()).hexdigest()

    def post(self, endpoint: str, body: dict, calls: list[Call]) -> dict:
        if endpoint not in {"search", "contents"}:
            raise ValueError("only search and contents are supported")

        def record(attempt, status, start, usd=None, basis="unknown", cached=False):
            call = Call(endpoint, attempt, status, (time.monotonic() - start) * 1000, usd, basis, cached)
            calls.append(call)
            LOG.info(json.dumps({"event": "exa_call", "mode": self.mode, **asdict(call)}))

        if self.cache:
            start = time.monotonic()
            key = hashlib.sha256(json.dumps([self.namespace, endpoint, body], sort_keys=True).encode()).hexdigest()
            hit = self.cache.get(key)
            if hit is not None:
                record(0, "cache", start, 0.0, "cache", True)
                return hit

        for attempt in range(1, 4):
            with self.semaphore:
                start = time.monotonic()
                try:
                    response = self.http.post("/" + endpoint, json=body)
                except httpx.RequestError as exc:
                    record(attempt, type(exc).__name__, start)
                    raise ApiError(f"{endpoint}: {type(exc).__name__}") from None
            status = response.status_code
            if status == 200:
                try:
                    data = response.json()
                    if (not isinstance(data, dict) or not isinstance(data.get("results"), list)
                            or not all(isinstance(r, dict) for r in data["results"])
                            or not isinstance(data.get("statuses", []), list)
                            or not all(isinstance(s, dict) for s in data.get("statuses", []))):
                        raise ValueError
                except (ValueError, UnicodeError):
                    record(attempt, "bad_response", start)
                    raise ApiError(f"{endpoint}: invalid response") from None
                usd, basis = cost(endpoint, body, data)
                record(attempt, status, start, usd, basis)
                if self.cache and all(s.get("status") == "success" for s in data.get("statuses", [])):
                    self.cache.put(key, data)
                return data

            record(attempt, status, start)
            floor = retry_floor(response.headers.get("Retry-After"))
            if (status != 429 and not 500 <= status < 600) or attempt == 3 or floor > 10:
                raise ApiError(f"{endpoint}: HTTP {status}")
            self.sleep(floor + random.uniform(0, 0.5 * 2 ** (attempt - 1)))
        raise AssertionError("unreachable")
