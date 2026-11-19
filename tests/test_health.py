from datetime import date
import pytest

from exa_fde_kit.health import scores, synthetic

END = date(2026, 11, 19)


def test_synthetic_tenants_compared_only_to_their_own_prior_week():
    rows = list(synthetic(END))
    assert all(r["mode"] == "synthetic" for r in rows)
    by = {r["tenant"]: r for r in scores(rows, END, "synthetic")}
    assert scores(rows, END, "live") == []
    stable, slipping, silent = by["steady"], by["slipping"], by["silent"]
    assert (stable["active_days"], stable["previous_queries"], stable["queries"]) == (7, 28, 28)
    assert stable["health_score"] == 100 and not stable["churn_risk"]
    assert slipping["queries"] == 6 and slipping["query_trend"] == pytest.approx(6/28 - 1)
    assert slipping["bad_answer_share"] == pytest.approx(4/6)
    assert slipping["error_rate"] == slipping["rate_429"] == pytest.approx(3/9)
    assert slipping["p95_drift"] == 2 and slipping["churn_risk"]
    assert silent["queries"] == 0 and silent["churn_risk"] and silent["rate_429"] is None


def test_unassessed_answers_and_unknown_baselines_are_not_successes():
    rows = [{"event": "exa_answer", "timestamp": "2026-11-20T00:01:00+02:00", "tenant": "new",
             "mode": "live", "quality": "unassessed", "latency_ms": 10}]
    report, = scores(rows, END, "live")
    assert report["active_days"] == report["queries"] == 1
    assert report["query_trend"] is None and report["p95_drift"] is None
    assert report["bad_answer_share"] is None and report["assessed_answers"] == 0
    assert report["health_score"] is None and report["churn_risk"] is None


def test_only_complete_window_and_valid_attribution():
    rows = list(synthetic(END))
    old = {**rows[0], "tenant": "ancient", "timestamp": "2025-01-01T00:00:00+00:00"}
    assert scores([old], END, "synthetic") == []
    with pytest.raises(ValueError, match="tenant"):
        scores([{**rows[0], "tenant": ""}], END, "synthetic")
    with pytest.raises(ValueError, match="timestamp"):
        scores([{**rows[0], "timestamp": "2026-11-19"}], END, "synthetic")
