import io
import json

import httpx

from exa_fde_kit.client import Client
from exa_fde_kit.evaluation import load_cases
from exa_fde_kit.mcp_server import serve
from exa_fde_kit.replay import replay_transport


def request(i, method, **params):
    return {"jsonrpc": "2.0", "id": i, "method": method, "params": params}


INIT = request(1, "initialize", protocolVersion="2025-11-25", capabilities={}, clientInfo={"name": "test", "version": "1"})
READY = {"jsonrpc": "2.0", "method": "notifications/initialized"}


def exchange(messages):
    wire = "".join(x + "\n" if isinstance(x, str) else json.dumps(x) + "\n" for x in messages)
    output = io.StringIO()
    with httpx.Client(transport=replay_transport(), base_url="https://replay.invalid") as http:
        serve(Client(http, mode="synthetic"), io.StringIO(wire), output)
    return [json.loads(line) for line in output.getvalue().splitlines()]


def test_in_process_client_negotiates_calls_and_reads_both_tools():
    q = next(c.question for c in load_cases() if c.id == "pg-index")
    init, listing, search, answer = exchange([INIT, READY, request(2, "tools/list"),
        request(3, "tools/call", name="search_with_citations", arguments={"query": q}),
        request(4, "tools/call", name="answer_with_evidence", arguments={"query": q})])
    assert init["result"]["protocolVersion"] == INIT["params"]["protocolVersion"]
    assert {t["name"] for t in listing["result"]["tools"]} == {"search_with_citations", "answer_with_evidence"}
    hits = json.loads(search["result"]["content"][0]["text"])
    assert hits["mode"] == "synthetic" and len(hits["sources"]) == 3
    evidence = json.loads(answer["result"]["content"][0]["text"])["evidence"]
    assert any("CONCURRENTLY" in p["text"] and "postgresql.org" in p["url"] for p in evidence)


def test_protocol_and_tool_errors_are_distinct_and_connection_survives():
    bad, early, init, invalid, missing, provider, ping = exchange(["not json", request(0, "tools/list"), INIT, READY,
        request(2, "tools/call", name="answer_with_evidence", arguments={"query": ""}),
        request(3, "tools/call", name="other", arguments={"query": "x"}),
        request(4, "tools/call", name="search_with_citations", arguments={"query": "not recorded"}), request(5, "ping")])
    assert bad["error"]["code"] == -32700 and "error" in early
    assert invalid["result"]["isError"] and missing["error"]["code"] == -32602
    assert provider["result"]["isError"] and ping["result"] == {}
