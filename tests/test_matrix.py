"""Exercise the CLI through the real replay transport; APJ has no replay cassette."""

import json
import pytest

from exa_fde_kit.evaluation import load_cases, matrix_main
from exa_fde_kit.report_html import merge_reports


def test_multilingual_labels_and_matrix_offline(tmp_path):
    cases = load_cases("apj")
    assert len(cases) == len({c.id for c in cases}) == 24
    assert {c.language for c in cases} == {"ja", "ko", "hi", "id", "zh-Hans", "vi", "en"}
    assert all(
        c.verification_url.startswith("https://") and c.verified_on and c.verified_fact
        for c in cases
    )
    out = tmp_path / "example.html"
    assert (
        matrix_main(
            [
                "--offline",
                "--limit",
                "2",
                "--presets",
                "lite,router",
                "--repeat",
                "2",
                "--output",
                str(out),
            ]
        )
        == 0
    )
    assert "SYNTHETIC" in out.read_text()
    with pytest.raises(SystemExit):
        matrix_main(["--offline", "--dataset", "apj"])


def test_ask_router_is_available_without_credentials(monkeypatch, capsys):
    import sys
    from exa_fde_kit.cli import main

    monkeypatch.delenv("EXA_API_KEY", raising=False)
    monkeypatch.setattr(
        sys,
        "argv",
        [
            "exa-fde-kit",
            "ask",
            "--case",
            "pg-index",
            "--offline",
            "--preset",
            "router",
            "--router-usd",
            "0",
        ],
    )
    assert main() == 0
    out = capsys.readouterr().out
    assert "budget" in out and "abstaining" in out


def test_merge_windows_offline_without_rebuying_data(tmp_path):
    paths = []
    for window in ("morning", "evening"):
        path = tmp_path / (window + ".jsonl")
        rows = [
            dict(
                mode="live",
                dataset="english",
                case="pg-index",
                window=window,
                preset=preset,
                recall=1,
                supported=preset == "summary",
                latency_ms=500,
                usd=0.007,
                unknown_costs=0,
                escalated=False,
                error=False,
                blank=False,
            )
            for preset in ("lite", "summary")
        ]
        path.write_text("".join(json.dumps(row) + "\n" for row in rows))
        paths.append(path)
    report = merge_reports(paths, "lite")
    assert "morning" in report and "evening" in report and "+100.0" in report
    assert "summary" not in merge_reports(paths, "lite", {"lite"})
    with pytest.raises(ValueError, match="no observations"):
        merge_reports(paths, "lite", {"lite", "typo"})
    with pytest.raises(ValueError, match="duplicate"):
        merge_reports([paths[0], paths[0]], "lite")
    paths[1].write_text(paths[1].read_text().replace('"live"', '"synthetic"'))
    with pytest.raises(ValueError, match="same dataset and mode"):
        merge_reports(paths, "lite")


@pytest.mark.parametrize(
    "field,value",
    [
        ("usd", -1),
        ("supported", "false"),
        ("recall", 2.0),
        ("latency_ms", float("nan")),
        ("unknown_costs", -1),
    ],
)
def test_bad_metric_files_fail_closed(tmp_path, field, value):
    row = dict(
        mode="live",
        dataset="english",
        case="q",
        preset="lite",
        window="one",
        recall=1,
        supported=False,
        latency_ms=20,
        usd=0.007,
        unknown_costs=0,
        escalated=False,
        error=False,
        blank=True,
    )
    row[field] = value
    path = tmp_path / "bad.jsonl"
    path.write_text(json.dumps(row))
    with pytest.raises(ValueError, match="invalid observation"):
        merge_reports([path], "lite")
