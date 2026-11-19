"""Exercise actual transport admission, not a semaphore's private state."""
from concurrent.futures import ThreadPoolExecutor
from datetime import datetime, timedelta
import json
import threading
import time

import httpx
import pytest

from exa_fde_kit.client import ApiError, Client


def test_paced_workers_and_timestamp(caplog):
    starts = []
    def reply(_):
        starts.append(time.monotonic())
        return httpx.Response(200, json={"results": []})
    with httpx.Client(base_url="https://mock.invalid", transport=httpx.MockTransport(reply)) as http:
        c = Client(http, qps=20)
        with caplog.at_level("INFO", logger="exa_fde_kit"), ThreadPoolExecutor(4) as pool:
            list(pool.map(lambda _: c.post("search", {"type": "lite"}, []), range(4)))
    assert min(b - a for a, b in zip(starts, starts[1:])) >= .04
    assert all(datetime.fromisoformat(json.loads(r.message)["timestamp"]).utcoffset() == timedelta(0)
               for r in caplog.records if r.name == "exa_fde_kit")


def test_cooldown_applies_to_new_workers():
    starts, backoff = [], threading.Event()
    def reply(_):
        starts.append(time.monotonic())
        if len(starts) == 1:
            return httpx.Response(429, headers={"Retry-After": "1"})
        return httpx.Response(200, json={"results": []})
    def pause(_):
        backoff.set()
    with httpx.Client(base_url="https://mock.invalid", transport=httpx.MockTransport(reply)) as http:
        c = Client(http, sleep=pause)
        with ThreadPoolExecutor(2) as pool:
            first = pool.submit(c.post, "search", {"type": "lite"}, [])
            assert backoff.wait(2)
            c.post("search", {"type": "lite"}, [])
            first.result()
    assert len(starts) == 3 and min(starts[1:]) - starts[0] >= .99


def test_long_cooldown_rejects_without_more_http():
    attempts = []
    def reply(req):
        attempts.append(req)
        return httpx.Response(429, headers={"Retry-After": "900"})
    with httpx.Client(base_url="https://mock.invalid", transport=httpx.MockTransport(reply)) as http:
        c = Client(http)
        for _ in range(2):
            with pytest.raises(ApiError):
                c.post("search", {"type": "lite"}, [])
    assert len(attempts) == 1
