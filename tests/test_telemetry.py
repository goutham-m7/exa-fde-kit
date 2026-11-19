import io
import json
import logging

import httpx
import pytest

from exa_fde_kit.agent import research
from exa_fde_kit.client import Client
from exa_fde_kit.telemetry import events, prometheus, query_trace, record_answer


def test_prometheus_counts_attempts_not_answers_or_cache_hits():
    def row(status, ms, usd):
        return {"event": "exa_call", "mode": "live", "endpoint": "search", "status": status,
                "latency_ms": ms, "usd": usd, "cached": status == "cache"}
    output = prometheus([row(429, 50, None), row(200, 51, .007), row("cache", 2, 0), {"event": "exa_answer"}])
    lbl = '{mode="live",endpoint="search"}'
    assert f'exa_requests_total{lbl} 2\n' in output
    for name in ("errors", "rate_limited", "unknown_cost", "cache_hits"):
        assert f'exa_{name}_total{lbl} 1\n' in output
    assert 'exa_attempt_seconds_bucket{mode="live",endpoint="search",le="0.05"} 1' in output
    assert 'exa_attempt_seconds_bucket{mode="live",endpoint="search",le="+Inf"} 2' in output
    assert f'exa_known_cost_usd_total{lbl} 0.007' in output


def test_correlated_attempts_and_answer_do_not_log_input(caplog):
    with httpx.Client(base_url="https://replay.invalid", transport=httpx.MockTransport(
            lambda _: httpx.Response(200, json={"results": []}))) as http:
        with caplog.at_level(logging.INFO, logger="exa_fde_kit"), query_trace("team-a"):
            c = Client(http, mode="synthetic")
            record_answer(research(c, "private question"), c.mode)
    records = [json.loads(r.message) for r in caplog.records if r.name == "exa_fde_kit"]
    assert [r["event"] for r in records] == ["exa_call", "exa_answer"]
    assert records[0]["tenant"] == records[1]["tenant"] == "team-a"
    assert records[0]["trace_id"] == records[1]["trace_id"] and len(records[0]["span_id"]) == 16
    assert records[1]["quality"] == "blank" and "private question" not in str(records)


def test_invalid_rows_fail_with_redacted_diagnostic():
    with pytest.raises(ValueError, match="line 2") as exc:
        list(events(io.StringIO('{}\nprivate question\n')))
    assert "private question" not in str(exc.value)
    with pytest.raises(ValueError):
        prometheus([{"event": "exa_call", "endpoint": "search", "mode": "live", "status": 200,
                     "cached": False, "usd": -.001, "latency_ms": 10}])
