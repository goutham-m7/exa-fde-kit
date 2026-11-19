"""Extractive question answering. Never treat retrieved text as instructions."""

from __future__ import annotations

import re
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

    def __post_init__(self) -> None:
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
    # One candidate per distinct returned URL, including runners-up used by the router.
    passages: list[Citation] = field(default_factory=list)


def public_link(value: object) -> bool:
    if not isinstance(value, str) or any(not c.isprintable() or c.isspace() for c in value):
        return False
    try:
        parts = urlsplit(value)
        return parts.scheme in {"https", "http"} and bool(parts.hostname) and parts.username is None
    except ValueError:
        return False


_COMMON = set("the and for from with this that which what how does should can use are into without".split())
_CJK = re.compile(r"[\u3040-\u30ff\u3400-\u9fff]+")


def terms(text: str) -> set[str]:
    # Japanese and Chinese runs do not have whitespace-separated word boundaries.
    folded = text.casefold()
    result = {t for t in re.findall(r"\w+", _CJK.sub(" ", folded)) if len(t) > 2 and t not in _COMMON}
    for run in _CJK.findall(folded):
        result.update(run[i:i + 2] for i in range(max(1, len(run) - 1)))
    return result


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
            options: dict[str, str | int] = {"query": question}
            if config.mode == "highlights":
                options["maxCharacters"] = 700
            pages = client.post("contents", {"ids": a.urls, config.mode: options}, a.calls)
            failed = {s["id"] for s in pages.get("statuses", [])
                      if isinstance(s.get("id"), str) and s.get("status") != "success"}
            by_url = {key: r for r in pages["results"]
                      if isinstance(key := r.get("id") or r.get("url"), str)}
            query_terms = terms(question)
            candidates: dict[str, tuple[int, Citation]] = {}
            for url in a.urls:
                r = by_url.get(url, {})
                actual = r.get("url")
                if url in failed or not public_link(actual) or actual in failed:
                    continue
                chunks = r.get("highlights") if config.mode == "highlights" else [r.get("summary")]
                if not isinstance(chunks, list):
                    continue
                for chunk in chunks:
                    if isinstance(chunk, str):
                        text = " ".join("".join(c for c in chunk if c.isprintable() or c.isspace()).split())
                        text = text[:700]
                        rank = len(query_terms & terms(text))
                        if text and (actual not in candidates or rank > candidates[actual][0]):
                            candidates[actual] = (rank, Citation(actual, text))
            if candidates:
                # Keep equally strong evidence in retrieval order. If the query was paraphrased
                # and no terms overlap, defer to search rank rather than guessing a new rank.
                best = max(rank for rank, _ in candidates.values())
                a.passages = [c for _, c in candidates.values()]
                a.citations = [c for rank, c in candidates.values() if rank == best][:3 if best else 1]
    except ApiError as exc:
        a.error = str(exc)
    a.elapsed_ms = (monotonic() - start) * 1000
    return a
