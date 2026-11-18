"""Command-line interface. Offline mode never constructs a live transport."""

import argparse
import logging
import os
from pathlib import Path
import sqlite3
import sys

import httpx

from .agent import research
from .client import Client, LOG
from .evaluation import PRESETS, evaluate, load_cases, report
from .replay import replay_transport


def main() -> int:
    parser = argparse.ArgumentParser(prog="exa-fde-kit", description="Cited research for a developer support desk")
    sub = parser.add_subparsers(dest="cmd", required=True)
    ask = sub.add_parser("ask", help="retrieve short, cited evidence or abstain")
    question = ask.add_mutually_exclusive_group(required=True)
    question.add_argument("question", nargs="?")
    question.add_argument("--case", choices=[c.id for c in load_cases()])
    ask.add_argument("--preset", choices=PRESETS, default="baseline")
    ask.add_argument("--no-cache", action="store_true", help="do not persist request results")
    bench = sub.add_parser("eval", help="run the benchmark; live mode can incur charges")
    bench.add_argument("--preset", choices=PRESETS, help="only run this preset (default: all five)")
    bench.add_argument("--limit", type=int, choices=range(1, len(load_cases()) + 1), metavar="N")
    bench.add_argument("--output", type=Path, help="default: reports/{synthetic,live}.md")
    for p in [ask, bench]:
        p.add_argument("--offline", action="store_true", help="use synthetic recordings without network access")
        p.add_argument("--log-calls", action="store_true", help="emit JSON attempt telemetry in offline mode too")
    args = parser.parse_args()
    key = None if args.offline else os.environ.get("EXA_API_KEY", "").strip()
    if not args.offline and not key:
        print("Live mode requires EXA_API_KEY. Use --offline for synthetic replay.", file=sys.stderr)
        return 2
    if not args.offline or args.log_calls:
        if not LOG.handlers:
            handler = logging.StreamHandler()
            handler.setFormatter(logging.Formatter("%(message)s"))
            LOG.addHandler(handler)
        LOG.setLevel(logging.INFO)
        LOG.propagate = False

    cache_dir = None
    if args.cmd == "ask" and not args.offline and not args.no_cache:
        cache_dir = Path(os.getenv("XDG_CACHE_HOME") or Path.home() / ".cache") / "exa-fde-kit"
    try:
        with httpx.Client(base_url="https://api.exa.ai", headers={"x-api-key": key} if key else {},
                          timeout=httpx.Timeout(15, connect=4), follow_redirects=False,
                          transport=replay_transport() if args.offline else None) as http:
            client = Client(http, cache_dir=cache_dir, mode="synthetic" if args.offline else "live")
            if args.cmd == "ask":
                q = args.question or next(c.question for c in load_cases() if c.id == args.case)
                a = research(client, q, PRESETS[args.preset])
                label = "SYNTHETIC FIXTURE — not live evidence" if args.offline else "LIVE SOURCES (local cache may apply)"
                print(f"{label}\n{q}\n")
                if a.error:
                    print(a.error, file=sys.stderr)
                    if args.offline:
                        print("Use --case for a recorded question.", file=sys.stderr)
                if not a.citations:
                    print("No usable evidence; abstaining.")
                else:
                    view = "Source summaries (generated, not direct quotes)" if PRESETS[args.preset].mode == "summary" else "Source passages"
                    print(view)
                    for i, cite in enumerate(a.citations, 1):
                        print(f"[{i}] {cite.text}")
                    print("\nSources")
                    for i, cite in enumerate(a.citations, 1):
                        print(f"[{i}] {cite.url}")
                return int(bool(a.error))

            names = [args.preset] if args.preset else list(PRESETS)
            trials = evaluate(client, load_cases()[:args.limit], names)
            out = args.output or Path("reports") / ("synthetic.md" if args.offline else "live.md")
            text = report(trials, names, args.offline)
            out.parent.mkdir(parents=True, exist_ok=True)
            out.write_text(text, encoding="utf-8")
            print(text.partition("## Case audit")[0].rstrip())
            print(f"\nCase-by-case report: {out}")
            return int(any(t.answer.error for t in trials))
    except (OSError, sqlite3.Error, ValueError) as exc:
        print(f"Unable to complete command: {exc}", file=sys.stderr)
        return 2
