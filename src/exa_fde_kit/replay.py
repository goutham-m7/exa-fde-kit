"""Replay a checked-in synthetic cassette at the HTTP boundary. Never open a socket."""

import json
from importlib.resources import files

import httpx


def replay_transport() -> httpx.MockTransport:
    cassette = json.loads(files(__package__).joinpath("data/synthetic.json").read_bytes())
    pages = cassette["pages"]
    by_url = {page["url"]: page for page in pages.values()}

    def replay(request: httpx.Request) -> httpx.Response:
        body = json.loads(request.content)
        if request.method == "POST" and request.url.path == "/search":
            order = cassette["queries"].get(body["query"], {}).get(body["type"])
            if order is not None:
                ranked = (pages[key] for key in order)
                cutoff = body.get("startPublishedDate", "")[:10]
                hits = [{"id": p["id"], "url": p["url"]} for p in ranked if p["publishedDate"] >= cutoff]
                return httpx.Response(200, json={"results": hits[:body["numResults"]]})
        if request.method == "POST" and request.url.path == "/contents":
            field = "highlights" if "highlights" in body else "summary"
            results = [{"id": url, "url": url, field: by_url[url][field]}
                       for url in body["ids"] if url in by_url]
            statuses = [{"id": url, "status": "success" if url in by_url else "error"} for url in body["ids"]]
            return httpx.Response(200, json={"results": results, "statuses": statuses})
        return httpx.Response(404, json={"error": "No synthetic recording"})

    return httpx.MockTransport(replay)
