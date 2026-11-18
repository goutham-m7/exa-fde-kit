import json
import threading
import time
from concurrent.futures import ThreadPoolExecutor

import httpx
import pytest

from exa_fde_kit.agent import Config, research
from exa_fde_kit.client import Client

URL = "https://docs.python.org/3/library/asyncio.html"
OTHER = "https://example.org/unrelated"


def client(fn, **kwargs):
    http = httpx.Client(transport=httpx.MockTransport(fn), base_url="https://api.exa.ai")
    return Client(http, **kwargs)


def test_rank_citations_and_wire_contract():
    def reply(req):
        body = json.loads(req.content)
        if req.url.path == "/search":
            assert body == {"query": "task groups?", "type": "lite", "numResults": 2,
                            "startPublishedDate": "2024-01-01T00:00:00Z"}
            return httpx.Response(200, json={"results": [{"url": URL}, {"url": OTHER}]})
        assert req.url.path == "/contents"
        assert body == {"ids": [URL, OTHER], "summary": {"query": "task groups?"}}
        return httpx.Response(200, json={"results": [{"url": OTHER, "summary": "bad"},
            {"url": URL, "summary": "TaskGroup waits for tasks."}],
            "statuses": [{"id": OTHER, "status": "error"}], "costDollars": {"total": 0.003}})

    a = research(client(reply), "task groups?", Config("lite", 2, "summary", "2024-01-01T00:00:00Z"))
    assert a.urls == [URL, OTHER]
    assert [(c.url, c.text) for c in a.citations] == [(URL, "TaskGroup waits for tasks.")]
    assert [c.usd for c in a.calls] == [0.004, 0.003]


@pytest.mark.parametrize("status,attempts", [(401, 1), (429, 3), (503, 3)])
def test_errors_are_bounded_and_do_not_leak(status, attempts, caplog):
    def fail(req):
        return httpx.Response(status, text="secret provider message")
    with caplog.at_level("INFO", logger="exa_fde_kit"):
        a = research(client(fail, sleep=lambda _: None), "sensitive input")
    assert a.error == f"search: HTTP {status}"
    assert len(a.calls) == attempts
    assert not a.citations and all(c.usd is None for c in a.calls)
    assert "secret provider message" not in caplog.text and "sensitive input" not in caplog.text
    events = [json.loads(r.message) for r in caplog.records if r.name == "exa_fde_kit"]
    assert len(events) == attempts and events[-1]["latency_ms"] >= 0


def test_retry_after_and_cache_survive_new_client(tmp_path):
    sleeps, requests = [], []
    def reply(req):
        requests.append(req.url.path)
        if len(requests) == 1:
            return httpx.Response(429, headers={"Retry-After": "1"})
        return httpx.Response(200, json={"results": []})
    for _ in range(2):
        a = research(client(reply, sleep=sleeps.append, cache_dir=tmp_path), "q")
    assert requests == ["/search", "/search"] and sleeps[0] >= 1
    assert not a.citations and a.calls[0].cached and a.calls[0].usd == 0


def test_slowdown_beyond_retry_budget_aborts():
    def reply(_):
        return httpx.Response(429, headers={"Retry-After": "900"})
    assert len(research(client(reply), "q").calls) == 1


def test_timeout_is_not_replayed():
    def fail(_):
        raise httpx.ReadTimeout("unknown whether charged")
    a = research(client(fail), "q")
    assert a.error and len(a.calls) == 1 and a.calls[0].usd is None


def test_concurrency_limit():
    lock = threading.Lock()
    active = peak = 0
    def slow(_):
        nonlocal active, peak
        with lock:
            active += 1
            peak = max(active, peak)
        time.sleep(0.025)
        with lock:
            active -= 1
        return httpx.Response(200, json={"results": []})
    c = client(slow, concurrency=2)
    with ThreadPoolExecutor(max_workers=6) as pool:
        list(pool.map(lambda n: research(c, str(n)), range(8)))
    assert peak == 2


def test_select_relevant_evidence_over_off_topic_search_hit():
    def reply(req):
        if req.url.path == "/search":
            return httpx.Response(200, json={"results": [{"url": OTHER}, {"url": URL}]})
        return httpx.Response(200, json={"results": [
            {"url": OTHER, "highlights": ["See the release notes for details."]},
            {"url": URL, "highlights": ["An overview.", "An asyncio timeout bounds work."]},
        ]})
    a = research(client(reply), "How do I use an asyncio timeout?")
    assert a.urls == [OTHER, URL]
    assert [(c.url, c.text) for c in a.citations] == [(URL, "An asyncio timeout bounds work.")]


def test_cache_ttl_and_key_isolation(tmp_path, monkeypatch):
    n = 0

    def reply(_):
        nonlocal n
        n += 1
        return httpx.Response(200, json={"results": []})

    now = 1000
    monkeypatch.setattr(time, "time", lambda: now)
    for credential, expected_requests in (("test-key-a", 1), ("test-key-b", 2), ("test-key-a", 2)):
        with httpx.Client(transport=httpx.MockTransport(reply), base_url="https://api.exa.ai",
                          headers={"x-api-key": credential}) as http:
            c = Client(http, cache_dir=tmp_path)
            research(c, "same query")
            assert n == expected_requests
            if credential == "test-key-a" and expected_requests == 2:
                now += 3601
                research(c, "same query")
                assert n == 3


def test_invalid_provider_payload_abstains_without_logging_body():
    a = research(client(lambda _: httpx.Response(200, json={"unexpected": "private"})), "q")
    assert a.error == "search: invalid response"
    assert not a.citations and a.calls[0].usd is None


def test_non_retrieval_api_call_refused():
    c = client(lambda _: pytest.fail("unexpected network attempt"))
    with pytest.raises(ValueError, match="only search and contents"):
        c.post("other", {}, [])
