import json
import socket
import sys

import httpx
import pytest

from exa_fde_kit.agent import Answer, Citation
from exa_fde_kit.cli import main
from exa_fde_kit.evaluation import Case, load_cases, percentile, score
from exa_fde_kit.replay import replay_transport


def test_denominators_and_domain_boundaries():
    c = Case("id", "question", ["docs.test", "another.test"], ["retry-after"])
    urls = ["https://evildocs.test", "https://api.docs.test/a", "https://another.test/a"]
    a = Answer(urls=urls, citations=[Citation(urls[0], "Retry-After"),
                                    Citation(urls[1], "Retry-After"), Citation(urls[2], "No match")])
    assert score(c, a, 2) == (0.5, 1)
    assert score(c, Answer(), 3) == (0.0, 0)
    assert percentile([3, 1, 4, 2], .5) == 2
    assert percentile([3, 1, 4, 2], .95) == 4


def test_replay_has_no_live_fallback():
    with httpx.Client(transport=replay_transport(), base_url="https://api.exa.ai") as http:
        res = http.post("/search", json={"query": "not a recorded question", "type": "auto", "numResults": 3})
        assert res.status_code == 404


def test_full_offline_report_without_key_or_socket(tmp_path, monkeypatch, capsys):
    monkeypatch.delenv("EXA_API_KEY", raising=False)
    def no_connect(*args):
        pytest.fail("offline replay opened a network connection")
    monkeypatch.setattr(socket.socket, "connect", no_connect)
    path = tmp_path / "report.md"
    monkeypatch.setattr(sys, "argv", ["exa-fde-kit", "eval", "--offline", "--output", str(path)])
    assert main() == 0
    report = path.read_text()
    assert "SYNTHETIC" in report and "not Exa latency" in report
    assert "recall@k" in report and "p95" in report and "USD" in report
    for name in ("baseline", "lite", "wide", "summary", "recent"):
        assert f"| {name} | 24 |" in report
    assert len(load_cases()) == len({c.id for c in load_cases()}) == 24


def test_live_execution_requires_key(monkeypatch, capsys):
    monkeypatch.delenv("EXA_API_KEY", raising=False)
    monkeypatch.setattr(sys, "argv", ["exa-fde-kit", "ask", "question"])
    assert main() == 2
    assert "EXA_API_KEY" in capsys.readouterr().err
