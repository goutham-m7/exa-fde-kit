"""Signed synthetic Websets deliveries. No key or Exa resources."""
import hashlib
import hmac
import json
import threading
import time
from datetime import date

import httpx
import pytest

from exa_fde_kit.monitor import Inbox, canonical, definition, receiver, verified

KEY = b"local-test-secret"
DAY = date(2026, 11, 19)


def delivery(event="evt_a", item="it_a", url="https://NEWS.example:443/a?utm_medium=mail#read", webset="ws_a"):
    return json.dumps({"id": event, "type": "webset.item.created", "createdAt": "2026-11-18T21:00:00-05:00",
                       "data": {"id": item, "websetId": webset, "properties": {"type": "article", "url": url,
                                "article": {"title": "A [new] round"}}}}).encode()


def signature(body, ts):
    return f"t={ts},v1=" + hmac.new(KEY, str(ts).encode() + b"." + body, hashlib.sha256).hexdigest()


def test_signature_rotation_raw_bytes_and_window():
    body = delivery()
    sig = signature(body, 1000)
    assert verified(body, sig.replace("v1=", "v1=" + "0" * 64 + ",v1="), KEY, 1300)
    assert not verified(body + b" ", sig, KEY, 1000)
    assert not verified(body, sig, KEY, 699)
    assert not verified(body, sig, KEY, 1301)
    for bad in ["", sig + ",t=1000", "t=oops,v1=x", "t=1000,v1=ä"]:
        assert not verified(body, bad, KEY, 1000)


def test_scoped_receipts_and_identity_aliases_survive_restart(tmp_path):
    path = tmp_path / "db"
    inbox = Inbox(path, "ws_a")
    assert inbox.ingest(delivery(webset="ws_other")) == "ignored"
    assert inbox.ingest(delivery()) == "added"
    again = Inbox(path, "ws_a")
    assert again.ingest(delivery()) == "duplicate"
    assert again.ingest(delivery("evt_b", "it_b", "https://news.example/a")) == "duplicate"
    assert again.ingest(delivery("evt_c", "it_b", "https://news.example/moved")) == "duplicate"
    assert again.ingest(delivery("evt_d", "it_c", "https://news.example/a?id=2")) == "added"
    md = again.digest(DAY)
    assert md.count("\n- ") == 2 and "utm_" not in md and r"A \[new\] round" in md
    assert "No new articles" in again.digest(date(2026, 11, 18))
    assert "No new articles" in Inbox(path, "ws_other").digest(DAY)


def test_invalid_payload_does_not_consume_receipt(tmp_path):
    inbox = Inbox(tmp_path / "db", "ws_a")
    with pytest.raises(ValueError):
        inbox.ingest(delivery(url="javascript:alert(1)"))
    assert inbox.ingest(delivery()) == "added"
    assert canonical("https://site.test/search?q=a%2Bb&gclid=x") == "https://site.test/search?q=a%2Bb"


def test_receiver_verifies_before_json_and_ack_after_commit(tmp_path):
    inbox = Inbox(tmp_path / "db", "ws_a")
    with receiver(inbox, KEY, 0) as server:
        thread = threading.Thread(target=server.serve_forever, daemon=True)
        thread.start()
        try:
            with httpx.Client(base_url=f"http://127.0.0.1:{server.server_port}", trust_env=False) as c:
                assert c.post("/webhook", content=b"not JSON").status_code == 401
                body = delivery()
                headers = {"Exa-Signature": signature(body, int(time.time()))}
                assert c.post("/webhook", content=body, headers=headers).json() == {"status": "added"}
                assert c.post("/webhook", content=body, headers=headers).json() == {"status": "duplicate"}
                assert c.post("/webhook", content=body + b" ", headers=headers).status_code == 401
                assert c.post("/other", content=body, headers=headers).status_code == 404
            assert "news.example/a" in inbox.digest(DAY)
        finally:
            server.shutdown()
            thread.join()


def test_definition_subscribes_to_item_events_for_daily_article_monitor():
    hook, monitor = definition("ws_a", "https://receiver.example/webhook")
    assert hook["body"]["events"] == ["webset.item.created"]
    assert monitor["body"]["websetId"] == "ws_a"
    assert monitor["body"]["behavior"]["config"]["entity"] == {"type": "article"}
    assert monitor["body"]["cadence"] == {"cron": "0 7 * * *", "timezone": "Etc/UTC"}
    with pytest.raises(ValueError):
        definition("ws_a", "http://receiver.example/webhook")
