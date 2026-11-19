"""Privacy-limited JSON spans and a streaming Prometheus text exporter."""
from __future__ import annotations

from collections import defaultdict
from contextlib import contextmanager
from contextvars import ContextVar
from dataclasses import dataclass, field
from datetime import datetime, timezone
import json
import logging
import math
import re
import secrets
from typing import Iterable, Iterator, TextIO, TYPE_CHECKING

if TYPE_CHECKING:
    from .agent import Answer

_TRACE: ContextVar[tuple[str, str] | None] = ContextVar("exa_trace", default=None)
BOUNDS = (.01, .05, .1, .25, .5, 1., 2.5, 5., 10.)


@contextmanager
def query_trace(tenant: str):
    """Supply a non-identifying tenant slug; context is reset even on failure."""
    if not re.fullmatch(r"[A-Za-z0-9_-]{1,64}", tenant):
        raise ValueError("use a 1-64 character alphanumeric tenant slug (dash/underscore allowed)")
    token = _TRACE.set((tenant, secrets.token_hex(16)))
    try:
        yield
    finally:
        _TRACE.reset(token)


def span_fields() -> dict:
    trace = _TRACE.get()
    return {"timestamp": datetime.now(timezone.utc).isoformat(), "span_id": secrets.token_hex(8),
            "trace_id": trace[1] if trace else secrets.token_hex(16), **({"tenant": trace[0]} if trace else {})}


def record_answer(answer: Answer, mode: str, *, supported: bool | None = None) -> None:
    """One completion per query. Never infer factual support from citation presence."""
    quality = ("error" if answer.error else "blank" if not answer.citations else
               "unassessed" if supported is None else "supported" if supported else "unsupported")
    logging.getLogger("exa_fde_kit").info(json.dumps({"event": "exa_answer", "mode": mode,
        **span_fields(), "quality": quality, "latency_ms": answer.elapsed_ms}))


def events(stream: TextIO) -> Iterator[dict]:
    for n, line in enumerate(stream, 1):
        if not line.strip():
            continue
        try:
            row = json.loads(line)
            if not isinstance(row, dict):
                raise ValueError
        except (ValueError, RecursionError):
            raise ValueError(f"invalid JSON object on line {n}") from None
        yield row


def number(value, name: str) -> float:
    if type(value) not in (int, float) or not math.isfinite(value) or value < 0:
        raise ValueError(f"invalid {name}: expected nonnegative finite number")
    return value


@dataclass
class Counters:
    requests: int = 0
    errors: int = 0
    rate_limited: int = 0
    cache_hits: int = 0
    known_cost_usd: float = 0.
    unknown_cost: int = 0
    seconds: float = 0.
    buckets: list[int] = field(default_factory=lambda: [0] * len(BOUNDS))

    def observe(self, row: dict):
        if row.get("cached") is True:
            self.cache_hits += 1
            return
        if not isinstance(row.get("status"), (str, int)):
            raise ValueError("missing or invalid call status")
        self.requests += 1
        self.errors += row["status"] != 200
        self.rate_limited += row["status"] == 429
        if row.get("usd") is None:
            self.unknown_cost += 1
        else:
            self.known_cost_usd += number(row["usd"], "usd")
        seconds = number(row.get("latency_ms"), "latency_ms") / 1000
        self.seconds += seconds
        for i, bound in enumerate(BOUNDS):
            self.buckets[i] += seconds <= bound


def prometheus(rows: Iterable[dict]) -> str:
    groups = defaultdict(Counters)
    for row in rows:
        if row.get("event") == "exa_call":
            # Keep cardinality bounded; never expose a caller-supplied endpoint or tenant as a label.
            mode = row.get("mode") if row.get("mode") in ("live", "synthetic", "local") else "other"
            ep = row.get("endpoint") if row.get("endpoint") in ("search", "contents", "answer") else "other"
            groups[mode, ep].observe(row)
    metrics = {"requests": "HTTP attempts, including retries.", "errors": "Failed HTTP attempts.",
               "rate_limited": "Attempts rejected with HTTP 429.", "cache_hits": "Local cache hits, not HTTP attempts.",
               "known_cost_usd": "Reported or estimated cost subtotal (synthetic is modeled only).",
               "unknown_cost": "Attempts with unknown cost, excluded from the subtotal."}
    series = [(f'mode="{mode}",endpoint="{ep}"', groups[mode, ep]) for mode, ep in sorted(groups)]
    lines = []
    for name, description in metrics.items():
        metric = f"exa_{name}_total"
        lines.extend([f"# HELP {metric} {description}", f"# TYPE {metric} counter"])
        lines.extend(f"{metric}{{{labels}}} {getattr(group, name):.12g}" for labels, group in series)
    metric = "exa_attempt_seconds"
    lines.extend([f"# HELP {metric} HTTP attempt duration excluding admission and backoff.", f"# TYPE {metric} histogram"])
    for labels, g in series:
        for bound, count in zip(BOUNDS, g.buckets):
            lines.append(f'{metric}_bucket{{{labels},le="{bound:g}"}} {count}')
        lines.extend([f'{metric}_bucket{{{labels},le="+Inf"}} {g.requests}', f"{metric}_sum{{{labels}}} {g.seconds:.12g}",
                      f"{metric}_count{{{labels}}} {g.requests}"])
    return "\n".join(lines) + "\n"
