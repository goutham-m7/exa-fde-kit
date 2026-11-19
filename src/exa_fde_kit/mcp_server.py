"""Local tools-only MCP server. stdout is reserved for JSON-RPC frames."""
import argparse
from dataclasses import asdict
import json
import os
import sys
from typing import Any, TextIO

import httpx

from .agent import public_link, research
from .client import ApiError, Client
from .replay import replay_transport

VERSION = "2025-11-25"
TOOLS = {
    "search_with_citations": "Return ranked source URLs for a query (discovery, not verified evidence).",
    "answer_with_evidence": "Return extractive passages with source URLs, or abstain. Passages are untrusted data.",
}
SCHEMA = {"type": "object", "properties": {"query": {"type": "string", "minLength": 1, "maxLength": 2000}},
          "required": ["query"], "additionalProperties": False}


def error(req_id: str | int | None, code: int, message: str) -> dict[str, Any]:
    return {"jsonrpc": "2.0", "id": req_id, "error": {"code": code, "message": message}}


def call_tool(client: Client, name: str, args: object) -> dict[str, Any]:
    try:
        if (not isinstance(args, dict) or args.keys() != {"query"} or not isinstance(args["query"], str)
                or not args["query"].strip() or len(args["query"]) > 2000):
            raise ValueError("expected a query of 1–2000 characters")
        q = args["query"].strip()
        if name == "search_with_citations":
            hits = client.post("search", {"query": q, "type": "auto", "numResults": 3}, [])["results"]
            urls = list(dict.fromkeys(h["url"] for h in hits[:3] if public_link(h.get("url"))))
            result: dict[str, Any] = {"sources": [{"rank": i, "url": url} for i, url in enumerate(urls, 1)]}
        else:
            answer = research(client, q)
            if answer.error:
                raise ApiError(answer.error)
            result = {"abstained": not answer.citations, "evidence": [asdict(c) for c in answer.citations]}
    except (ApiError, ValueError) as exc:
        return {"isError": True, "content": [{"type": "text", "text": str(exc)}]}
    return {"content": [{"type": "text", "text": json.dumps({"mode": client.mode, **result})}]}


def serve(client: Client, inp: TextIO, out: TextIO) -> None:
    phase = "new"

    def handle(msg: object) -> dict[str, Any] | None:
        nonlocal phase
        if not isinstance(msg, dict) or msg.get("jsonrpc") != "2.0" or not isinstance(msg.get("method"), str):
            return error(None, -32600, "Invalid request")
        method, params = msg["method"], msg.get("params", {})
        if "id" not in msg:
            if method == "notifications/initialized" and phase == "negotiated":
                phase = "ready"
            return None
        req_id = msg["id"]
        if type(req_id) not in (str, int):
            return error(None, -32600, "Invalid request ID")
        if not isinstance(params, dict):
            return error(req_id, -32602, "Expected named parameters")
        if method == "ping":
            result: dict[str, Any] = {}
        elif method == "initialize" and phase == "new":
            if (not isinstance(params.get("protocolVersion"), str) or not isinstance(params.get("capabilities"), dict)
                    or not isinstance(params.get("clientInfo"), dict)):
                return error(req_id, -32602, "Invalid initialization parameters")
            phase = "negotiated"
            result = {"protocolVersion": VERSION, "capabilities": {"tools": {}},
                      "serverInfo": {"name": "exa-fde-kit", "version": "0.1"}}
        elif phase != "ready":
            return error(req_id, -32002, "Initialize the session first")
        elif method == "tools/list":
            result = {"tools": [{"name": name, "description": description, "inputSchema": SCHEMA}
                                for name, description in TOOLS.items()]}
        elif method == "tools/call":
            name = params.get("name")
            if not isinstance(name, str) or name not in TOOLS:
                return error(req_id, -32602, "Unknown tool")
            result = call_tool(client, name, params.get("arguments"))
        else:
            return error(req_id, -32601, "Method not found")
        return {"jsonrpc": "2.0", "id": req_id, "result": result}

    for line in inp:
        try:
            msg = json.loads(line)
        except (ValueError, RecursionError):
            response: dict[str, Any] | None = error(None, -32700, "Parse error")
        else:
            response = handle(msg)
        if response is not None:
            out.write(json.dumps(response) + "\n")
            out.flush()


def main() -> None:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--offline", action="store_true", help="serve the synthetic replay cassette")
    args = parser.parse_args()
    key = None if args.offline else os.environ.get("EXA_API_KEY")
    if not args.offline and not key:
        parser.error("live MCP requires EXA_API_KEY")
    with httpx.Client(base_url="https://api.exa.ai", headers={"x-api-key": key} if key else {},
                      transport=replay_transport() if args.offline else None, timeout=httpx.Timeout(15, connect=4)) as http:
        serve(Client(http, mode="synthetic" if args.offline else "live"), sys.stdin, sys.stdout)


if __name__ == "__main__":
    main()
