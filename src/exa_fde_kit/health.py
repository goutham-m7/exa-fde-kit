"""Explainable weekly tenant triage. Scores are rules, not churn probabilities."""
import argparse
from collections import defaultdict
from dataclasses import dataclass, field
from datetime import date, datetime, timedelta, timezone
import json
from pathlib import Path
from typing import Any, Iterable, Iterator

from .evaluation import percentile
from .telemetry import events, number


@dataclass
class Week:
    days: set[date] = field(default_factory=set)
    latencies: list[float] = field(default_factory=list)
    attempts: int = 0
    errors: int = 0
    limited: int = 0
    assessed: int = 0
    bad: int = 0

    def observe(self, row: dict[str, Any], day: date) -> None:
        if row["event"] == "exa_answer":
            quality = row.get("quality")
            if quality not in ("blank", "unsupported", "supported", "unassessed", "error"):
                raise ValueError("invalid answer quality")
            self.latencies.append(number(row.get("latency_ms"), "latency_ms"))
            self.days.add(day)
            self.assessed += quality in ("blank", "unsupported", "supported")
            self.bad += quality in ("blank", "unsupported")
        elif not row.get("cached", False):
            status = row.get("status")
            if type(status) not in (int, str):
                raise ValueError("invalid call status")
            self.attempts += 1
            self.errors += status != 200
            self.limited += status == 429


def ratio(a: float, b: float) -> float | None:
    return a / b if b else None


def score(tenant: str, prev: Week, cur: Week) -> dict[str, Any]:
    n, before = len(cur.latencies), len(prev.latencies)
    p95 = percentile(cur.latencies, .95) if n else None
    old_p95 = percentile(prev.latencies, .95) if before else None
    trend = ratio(n - before, before)
    drift = (p95 - old_p95) / old_p95 if p95 is not None and old_p95 else None
    err, limited, bad = ratio(cur.errors, cur.attempts), ratio(cur.limited, cur.attempts), ratio(cur.bad, cur.assessed)
    deductions = []
    if before >= 5 and trend is not None and trend <= -.4:
        deductions.append((30, "query volume fell at least 40%"))
    if len(prev.days) >= 3 and len(cur.days) <= 1:
        deductions.append((20, "activity fell to at most one day"))
    if cur.attempts >= 5 and err is not None and err >= .1:
        reason = "frequent 429s" if limited is not None and limited >= .1 else "high attempt error rate"
        deductions.append((20, reason))
    if cur.assessed >= 5 and bad is not None and bad >= .25:
        deductions.append((25, "at least one quarter of assessed answers blank or unsupported"))
    if min(n, before) >= 5 and drift is not None and drift >= .5:
        deductions.append((15, "end-to-end p95 rose at least 50%"))
    enough = max(n, before) >= 5
    value = max(0, 100 - sum(d for d, _ in deductions)) if enough else None
    return {"tenant": tenant, "active_days": len(cur.days), "previous_active_days": len(prev.days),
            "queries": n, "previous_queries": before, "query_trend": trend, "attempts": cur.attempts,
            "error_rate": err, "rate_429": limited, "assessed_answers": cur.assessed, "bad_answer_share": bad,
            "p95_ms": p95, "previous_p95_ms": old_p95, "p95_drift": drift, "health_score": value,
            "churn_risk": value <= 70 if value is not None else None,
            "reasons": [reason for _, reason in deductions] if enough else ["insufficient query volume"]}


def scores(rows: Iterable[dict[str, Any]], end: date, mode: str) -> list[dict[str, Any]]:
    tenants: defaultdict[str, tuple[Week, Week]] = defaultdict(lambda: (Week(), Week()))
    for row in rows:
        if row.get("event") not in ("exa_call", "exa_answer") or row.get("mode") != mode:
            continue
        try:
            stamp = datetime.fromisoformat(row["timestamp"])
            if stamp.tzinfo is None:
                raise ValueError
        except (KeyError, TypeError, ValueError):
            raise ValueError("expected a timezone-aware timestamp") from None
        day = stamp.astimezone(timezone.utc).date()
        age = (end - day).days
        if not 0 <= age < 14:
            continue
        tenant = row.get("tenant")
        if not isinstance(tenant, str) or not tenant.strip():
            raise ValueError("tenant missing; use traced answer and call logs")
        tenants[tenant][int(age < 7)].observe(row, day)
    return [score(tenant, *tenants[tenant]) for tenant in sorted(tenants)]


def synthetic(end: date) -> Iterator[dict[str, Any]]:
    """Deterministic two-week fixture: steady, declining and inactive cohorts."""
    sequence = 0
    for age in reversed(range(14)):
        for tenant in ("steady", "slipping", "silent"):
            count = 4 if age >= 7 or tenant == "steady" else 2 if tenant == "slipping" and age < 3 else 0
            for i in range(count):
                sequence += 1
                day = end - timedelta(days=age)
                common = {"mode": "synthetic", "tenant": tenant, "timestamp": f"{day}T12:00:0{i}Z",
                          "trace_id": f"{sequence:032x}"}
                slipping = age < 7 and tenant == "slipping"
                statuses = [429, 200] if slipping and i == 0 else [200]
                for attempt, status in enumerate(statuses, 1):
                    yield {**common, "event": "exa_call", "span_id": f"{sequence * 4 + attempt:016x}",
                           "endpoint": "search", "attempt": attempt, "status": status, "latency_ms": 20,
                           "cached": False, "usd": None if status == 429 else .007,
                           "cost_basis": "unknown" if status == 429 else "list_estimate"}
                quality = ("blank" if i == 0 else "unsupported") if slipping and age < 2 else "supported"
                yield {**common, "event": "exa_answer", "span_id": f"{sequence * 4:016x}", "quality": quality,
                       "latency_ms": 300 if slipping else 100}


def main() -> None:
    parser = argparse.ArgumentParser(description=__doc__)
    sub = parser.add_subparsers(dest="cmd", required=True)
    generate = sub.add_parser("generate", help="print synthetic multi-tenant JSONL")
    report = sub.add_parser("score", help="read tenant-attributed JSONL and print a weekly report")
    for p in (generate, report):
        p.add_argument("--end", type=date.fromisoformat, required=True, help="last included UTC day (YYYY-MM-DD)")
    report.add_argument("log", type=Path)
    report.add_argument("--mode", choices=("synthetic", "live"), default="live")
    args = parser.parse_args()
    try:
        if args.cmd == "generate":
            for row in synthetic(args.end):
                print(json.dumps(row))
        else:
            with args.log.open(encoding="utf-8") as stream:
                print(json.dumps({"week_end": str(args.end), "mode": args.mode,
                                  "tenants": scores(events(stream), args.end, args.mode)}, indent=2))
    except (ValueError, OSError) as exc:
        parser.exit(2, f"Cannot produce report: {exc}\n")


if __name__ == "__main__":
    main()
