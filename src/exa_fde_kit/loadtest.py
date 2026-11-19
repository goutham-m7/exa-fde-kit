"""Exercise the shared synchronous client under async demand. Loopback only."""
import argparse
import asyncio
from collections import deque
from http.server import BaseHTTPRequestHandler, HTTPServer
import json
from threading import Thread
import time
from typing import Any

import httpx

from .client import ApiError, Call, Client
from .evaluation import percentile


async def run_load(*, requests: int = 30, workers: int = 8, limit: int = 10,
                   paced: bool = True, busy_start: bool = True) -> dict[str, Any]:
    if not (1 <= requests <= 10000 and 1 <= workers <= 32 and 1 <= limit <= 100):
        raise ValueError("requests 1-10000, workers 1-32 and limit 1-100 required")
    # A single-threaded HTTP/1.0 responder owns the rolling window and arrival observations.
    accepted: deque[float] = deque()
    arrivals: list[tuple[float, int]] = []

    class Mock(BaseHTTPRequestHandler):
        def log_message(self, format: str, *args: object) -> None:
            pass

        def do_POST(self) -> None:
            if self.path != "/search":
                return self.send_error(404)
            self.rfile.read(int(self.headers["Content-Length"]))
            now = time.monotonic()
            if busy_start and not arrivals:
                accepted.extend([now] * limit)  # Simulate a quota just consumed by other account traffic.
            while accepted and now - accepted[0] >= 1:
                accepted.popleft()
            status = 429 if len(accepted) >= limit else 200
            arrivals.append((now, status))
            self.send_response(status)
            if status == 429:
                self.send_header("Retry-After", "1")
            else:
                accepted.append(now)
            body = b'{"results":[]}' if status == 200 else b'{}'
            self.send_header("Content-Type", "application/json")
            self.send_header("Content-Length", str(len(body)))
            self.end_headers()
            self.wfile.write(body)

    with HTTPServer(("127.0.0.1", 0), Mock) as server:
        thread = Thread(target=server.serve_forever, kwargs={"poll_interval": .05}, daemon=True)
        thread.start()
        try:
            # Never accept a URL, proxy, redirect, remote transport, credential or hostname override.
            with httpx.Client(base_url=f"http://127.0.0.1:{server.server_port}", trust_env=False,
                              follow_redirects=False, timeout=5) as http:
                client = Client(http, mode="local", concurrency=workers, qps=.98 * limit if paced else None)
                pending = iter(range(requests))
                elapsed: list[float] = []
                successes = retries = 0

                async def worker() -> None:
                    nonlocal successes, retries
                    for _ in pending:
                        calls: list[Call] = []
                        start = time.monotonic()
                        try:
                            await asyncio.to_thread(client.post, "search", {"type": "lite", "query": "synthetic load",
                                                                         "numResults": 1}, calls)
                            successes += 1
                        except ApiError:
                            pass  # Count terminal failures in the denominator and p95 below.
                        retries += sum(c.attempt > 1 for c in calls)
                        elapsed.append((time.monotonic() - start) * 1000)

                started = time.monotonic()
                await asyncio.gather(*(worker() for _ in range(min(workers, requests))))
                duration = time.monotonic() - started
        finally:
            server.shutdown()
            thread.join()

    window: deque[float] = deque()
    peak = 0
    for stamp, _ in arrivals:
        while window and stamp - window[0] >= .05:
            window.popleft()
        window.append(stamp)
        peak = max(peak, len(window))
    hits = [t for t, status in arrivals if status == 200]
    first_gap = next(((b[0] - a[0]) * 1000 for a, b in zip(arrivals, arrivals[1:]) if a[1] == 429), None)
    return {"mode": "loopback", "qps_limit": limit, "workers": workers, "paced": paced, "busy_start": busy_start,
            "requests": requests, "attempts": len(arrivals), "successes": successes, "errors": requests - successes,
            "retries": retries, "http_429": sum(status == 429 for _, status in arrivals), "peak_50ms": peak,
            "quiet_after_first_429_ms": first_gap, "goodput_qps": successes / duration,
            "steady_goodput_qps": (len(hits) - 1) / (hits[-1] - hits[0]) if len(hits) >= 2 else None,
            "p95_ms": percentile(elapsed, .95)}


def main() -> None:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--requests", type=int, default=30)
    parser.add_argument("--workers", type=int, default=8)
    parser.add_argument("--limit", type=int, default=10, help="server's rolling one-second QPS cap")
    parser.add_argument("--unpaced", action="store_true", help="control: leave cooldown enabled but disable pacing")
    parser.add_argument("--empty-start", action="store_true", help="start with a fresh quota rather than a 429")
    args = parser.parse_args()
    try:
        print(json.dumps(asyncio.run(run_load(requests=args.requests, workers=args.workers, limit=args.limit,
                                             paced=not args.unpaced, busy_start=not args.empty_start)), indent=2))
    except ValueError as exc:
        parser.error(str(exc))


if __name__ == "__main__":
    main()
