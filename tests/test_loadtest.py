import asyncio
import math

import pytest

from exa_fde_kit.loadtest import run_load


def test_shared_gate_recovers_after_busy_quota_window(monkeypatch):
    monkeypatch.setenv("HTTPS_PROXY", "http://invalid.test:1")
    monkeypatch.setenv("HTTP_PROXY", "http://invalid.test:1")
    report = asyncio.run(run_load(requests=16, workers=8, limit=10, paced=True, busy_start=True))
    assert report["mode"] == "loopback" and report["successes"] == 16 and report["errors"] == 0
    assert 1 <= report["retries"] <= 2 and report["http_429"] == report["retries"]
    assert report["attempts"] == 16 + report["retries"]
    assert report["peak_50ms"] <= math.ceil(10 * .05) + 1
    assert report["quiet_after_first_429_ms"] >= 990
    assert 7 < report["steady_goodput_qps"] < 11 and report["p95_ms"] >= 1000
    assert 0 < report["goodput_qps"] < report["steady_goodput_qps"]


@pytest.mark.parametrize("kwargs", [{"limit": 0}, {"workers": 0}, {"requests": 0}])
def test_invalid_load_arguments(kwargs):
    with pytest.raises(ValueError):
        asyncio.run(run_load(**kwargs))
