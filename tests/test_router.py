import json

import httpx
import pytest

from exa_fde_kit.client import Client
from exa_fde_kit.router import Budget, cascade


def routing_client(stages):
    requests = []

    def handle(req):
        body = json.loads(req.content)
        requests.append(body)
        if req.url.path == "/search":
            mode = body["type"]
            return httpx.Response(
                200,
                json={
                    "results": [
                        {"url": f"https://{i}.example{i}.org/{mode}"}
                        for i in range(len(stages[mode]))
                    ]
                },
            )
        mode = body["ids"][0].rsplit("/", 1)[-1]
        return httpx.Response(
            200,
            json={
                "results": [
                    {"url": url, "highlights": [text], "summary": text}
                    for url, text in zip(body["ids"], stages[mode])
                ]
            },
        )

    return Client(
        httpx.Client(base_url="https://api.exa.ai", transport=httpx.MockTransport(handle))
    ), requests


def test_router_stops_on_corroboration():
    c, requests = routing_client(
        {
            "lite": [
                "The pod readiness probe controls traffic.",
                "For pod traffic use the readiness probe.",
            ]
        }
    )
    r = cascade(c, "What controls pod traffic?")
    assert not r.escalated and len(requests) == 2 and r.answer.citations


@pytest.mark.parametrize(
    "initial,reason",
    [
        ([], "blank"),
        (["Entirely unrelated."], "no_support"),
        (["Pod traffic uses a readiness probe.", "Pod traffic arrives by train."], "low_agreement"),
    ],
)
def test_router_escalates_and_accounts_for_every_stage(initial, reason):
    c, requests = routing_client({"lite": initial, "auto": ["Pod traffic uses a readiness probe."]})
    r = cascade(c, "What controls pod traffic?")
    assert r.escalated and r.reason == reason
    assert len(r.answer.calls) == len(requests) and requests[-1].get("summary")
    assert r.answer.citations[0].url.endswith("/auto")


def test_router_budget_gates_before_spend():
    for budget in (Budget(0.006, 1000), Budget(0.007, 1000), Budget(0.1, 0)):
        c, requests = routing_client({"lite": []})
        r = cascade(c, "What controls pod traffic?", budget)
        assert not r.escalated and len(requests) <= 1
    with pytest.raises(ValueError):
        Budget(float("nan"), 100)


def test_no_upgrade_after_soft_deadline(monkeypatch):
    clock = iter([10.0, 10.2])
    monkeypatch.setattr("exa_fde_kit.router.monotonic", lambda: next(clock))
    client, requests = routing_client({"lite": []})
    route = cascade(client, "What controls traffic?", Budget(0.02, 100))
    assert route.reason == "budget" and not route.escalated and len(requests) == 1


def test_no_upgrade_on_auth_error():
    with httpx.Client(
        base_url="https://api.exa.ai", transport=httpx.MockTransport(lambda _: httpx.Response(401))
    ) as http:
        route = cascade(Client(http), "What controls pod traffic?")
    assert not route.escalated and route.answer.error == "search: HTTP 401"
    assert route.answer.calls[0].usd is None


def test_blank_upgrade_keeps_original_answer_and_all_charges():
    client, requests = routing_client(
        {"lite": ["A pod readiness probe controls traffic."], "auto": []}
    )
    route = cascade(client, "What controls pod traffic?")
    assert route.escalated and route.selected == "lite"
    assert route.answer.citations[0].url.endswith("/lite")
    assert len(requests) == len(route.answer.calls) == 3
