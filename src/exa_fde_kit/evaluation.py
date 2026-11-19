"""Paired, cold-cache benchmark with independent domain and evidence labels."""

from __future__ import annotations

import argparse
from dataclasses import asdict, dataclass
from datetime import datetime, timezone
from html import escape
from importlib.resources import files
import json
import os
from pathlib import Path
import random
import sys
from time import sleep
from statistics import mean
from urllib.parse import urlsplit

import httpx

from .agent import Answer, Config, research
from .client import Client
from .judge import contains_alias
from .replay import replay_transport
from .report_html import render
from .router import Budget, cascade
from .stats import Observation, percentile as percentile

PRESETS = {
    "baseline": Config(),
    "lite": Config(search_type="lite"),
    "wide": Config(k=5),
    "summary": Config(mode="summary"),
    "recent": Config(since="2024-01-01T00:00:00Z"),
    "lite-summary": Config(search_type="lite", mode="summary"),
}


@dataclass(frozen=True)
class Case:
    id: str
    question: str
    domains: list[str]
    aliases: list[str]
    language: str = "en"
    verification_url: str = ""
    verified_on: str = ""
    verified_fact: str = ""


def load_cases(dataset: str = "english") -> list[Case]:
    datasets = {"english": "cases.json", "apj": "apj.json"}
    if dataset not in datasets:
        raise ValueError(f"unknown dataset: {dataset}")
    data = files(__package__).joinpath("data", datasets[dataset]).read_bytes()
    return [Case(**row) for row in json.loads(data)]


def matches(url: str, domain: str) -> bool:
    host = (urlsplit(url).hostname or "").lower().rstrip(".")
    return host == domain or host.endswith("." + domain)


def score(case: Case, answer: Answer, k: int) -> tuple[float, int]:
    hits = sum(any(matches(url, d) for url in answer.urls[:k]) for d in case.domains)
    supported = sum(
        any(matches(c.url, d) for d in case.domains)
        and contains_alias(c.text, tuple(case.aliases))
        for c in answer.citations
    )
    return hits / len(case.domains), supported


@dataclass(frozen=True)
class Trial:
    name: str
    case: Case
    answer: Answer
    recall: float
    supported: int
    escalated: bool = False

    @property
    def known_usd(self) -> float:
        return sum(c.usd for c in self.answer.calls if c.usd is not None)

    def observation(self, window: str) -> Observation:
        return Observation(
            self.case.id, self.name, window, self.recall, bool(self.supported),
            self.answer.elapsed_ms, self.known_usd,
            sum(c.usd is None for c in self.answer.calls), self.escalated,
            bool(self.answer.error), not self.answer.citations,
        )


def evaluate(client: Client, cases: list[Case], names: list[str], *,
             seed: int = 42, budget: Budget = Budget()) -> list[Trial]:
    if client.cache:
        raise ValueError("benchmark must not share cached responses")
    rng = random.Random(seed)
    trials = []
    for case in cases:
        order = names.copy()
        rng.shuffle(order)
        for name in order:
            escalated = False
            if name == "router":
                route = cascade(client, case.question, budget)
                answer, escalated, k = route.answer, route.escalated, PRESETS["lite"].k
            else:
                config = PRESETS[name]
                answer, k = research(client, case.question, config), config.k
            trials.append(Trial(name, case, answer, *score(case, answer, k), escalated))
    return trials


def report(trials: list[Trial], names: list[str], offline: bool) -> str:
    label = "SYNTHETIC REPLAY — NOT LIVE" if offline else "LIVE API — cold client cache"
    note = ("Synthetic rankings, publication dates and passages. Timing is local replay, not Exa latency. "
            "USD is hypothetical list-price arithmetic; actual API spend is $0. No production conclusion follows."
            if offline else "Wall time is measured here. Costs are response-reported when available, otherwise estimated. "
            "Unknown charges on failed attempts are NOT included; reconcile with billing.")
    lines = [f"# Developer support retrieval eval: {label}", "", note, "",
             f"Run: {datetime.now(timezone.utc).isoformat(timespec='seconds')}. Same cases per preset; "
             "one serial pass, seeded order within each case (42). No client cache.", "",
             "| Preset | Cases | k | Domain recall@k | Supported cites | Supported answers | Blank | Errors | p50 ms | p95 ms | Known/est. USD | Unknown-cost attempts |",
             "|---|---:|---:|---:|---:|---:|---:|---:|---:|---:|---:|---:|"]
    for name in names:
        rows = [r for r in trials if r.name == name]
        times = [r.answer.elapsed_ms for r in rows]
        cited = sum(len(r.answer.citations) for r in rows)
        support = sum(r.supported for r in rows)
        k = PRESETS["lite" if name == "router" else name].k
        lines.append(f"| {name} | {len(rows)} | {k} | {mean(r.recall for r in rows):.1%} | "
                     f"{support}/{cited} | {sum(r.supported > 0 for r in rows)}/{len(rows)} | "
                     f"{sum(not r.answer.citations for r in rows)} | {sum(bool(r.answer.error) for r in rows)} | "
                     f"{percentile(times, .50):.2f} | {percentile(times, .95):.2f} | "
                     f"{sum(r.known_usd for r in rows):.4f} | "
                     f"{sum(c.usd is None for r in rows for c in r.answer.calls)} |")
    lines += ["", "Support is a proxy, not an entailment judge: an emitted passage must come from an expected "
              "domain and contain an independently labeled fact alias. Blank/error answers remain in the answer denominator. "
              "A blank answer has no citations and does not improve citation precision. Recall is the mean fraction of "
              "expected domains in the first k search results. Latencies include both stages, retries and failures (nearest rank).",
              "", "## Compared settings", ""]
    for name in names:
        if name == "router":
            routed = [t for t in trials if t.name == name]
            lines.append(f"- **router:** lite → auto + summaries; {sum(t.escalated for t in routed)}/{len(routed)} escalated.")
            continue
        cfg = PRESETS[name]
        lines.append(f"- **{name}:** {cfg.search_type}, k={cfg.k}, {cfg.mode}, published since {cfg.since or 'any time'}.")
    lines += ["", "## Case audit", "", "| Case | Preset | Expected domains | Recall | Supported / cited | Result |",
              "|---|---|---|---:|---:|---|"]
    for r in trials:
        status = r.answer.error or ("answer" if r.answer.citations else "abstain")
        lines.append(f"| {r.case.id} | {r.name} | {', '.join(r.case.domains)} | {r.recall:.0%} | "
                     f"{r.supported}/{len(r.answer.citations)} | {status} |")
    lines += ["", "## Inspect unsupported answers", "",
              "Evidence below is untrusted source text, not instructions. Compare it with the expected fact; "
              "a paraphrase can be useful even when the automatic check fails.", ""]
    for r in trials:
        if not r.answer.citations or r.supported == len(r.answer.citations):
            continue
        lines += [f"<details><summary>{r.case.id} · {r.name}</summary>", "",
                  f"Question: {r.case.question}", "", f"Expected fact aliases: {', '.join(r.case.aliases)}", ""]
        for c in r.answer.citations:
            lines.append(f"<pre>{escape(c.text)}\n{escape(c.url)}</pre>")
        lines += ["", "</details>", ""]
    return "\n".join(lines) + "\n"


def matrix_main(argv: list[str] | None = None) -> int:
    """Run paired cold-cache windows; require explicit opt-in for live charges."""
    parser = argparse.ArgumentParser(prog="python -m exa_fde_kit.evaluation")
    mode = parser.add_mutually_exclusive_group(required=True)
    mode.add_argument("--offline", action="store_true", help="synthetic English replay only")
    mode.add_argument("--live", action="store_true", help="charge EXA_API_KEY for each window")
    parser.add_argument("--dataset", choices=["english", "apj"], default="english")
    parser.add_argument("--presets", default=",".join([*PRESETS, "router"]))
    parser.add_argument("--baseline", help="paired comparison reference; default: first listed preset")
    parser.add_argument("--limit", type=int, choices=range(1, 25), default=24, metavar="N")
    parser.add_argument("--repeat", type=int, default=1, help="number of full windows")
    parser.add_argument("--wait-seconds", type=float, default=0, help="pause between windows")
    parser.add_argument("--router-usd", type=float, default=Budget.usd)
    parser.add_argument("--router-ms", type=float, default=Budget.latency_ms)
    parser.add_argument("--output", type=Path, default=Path("reports/matrix.html"))
    parser.add_argument("--observations", type=Path, help="also save per-case metrics (no source text)")
    args = parser.parse_args(argv)
    names = [s.strip() for s in args.presets.split(",")]
    baseline = args.baseline or names[0]
    if set(names) - {*PRESETS, "router"} or len(names) != len(set(names)) or baseline not in names:
        parser.error("choose unique known presets including the baseline")
    if args.repeat < 1 or not 0 <= args.wait_seconds < float("inf"):
        parser.error("repeat must be positive; wait must be finite and non-negative")
    if args.offline and args.dataset != "english":
        parser.error("only the English dataset has a synthetic cassette")
    if args.observations and args.output.resolve() == args.observations.resolve():
        parser.error("HTML and observation paths must differ")
    key = None if args.offline else os.environ.get("EXA_API_KEY", "").strip()
    if args.live and not key:
        parser.error("--live requires EXA_API_KEY")
    try:
        budget = Budget(args.router_usd, args.router_ms)
        cases = load_cases(args.dataset)[:args.limit]
        rows: list[Observation] = []
        with httpx.Client(base_url="https://api.exa.ai", headers={"x-api-key": key} if key else {},
                          timeout=httpx.Timeout(15, connect=4),
                          transport=replay_transport() if args.offline else None) as http:
            client = Client(http, mode="synthetic" if args.offline else "live")
            for i in range(args.repeat):
                if i:
                    sleep(args.wait_seconds)
                window = f"{i+1}: {datetime.now(timezone.utc).isoformat(timespec='seconds')}"
                trials = evaluate(client, cases, names, seed=42+i, budget=budget)
                rows.extend(trial.observation(window) for trial in trials)
        label = ("SYNTHETIC REPLAY (not Exa latency; actual spend $0)" if args.offline else "LIVE API")
        args.output.parent.mkdir(parents=True, exist_ok=True)
        args.output.write_text(render(rows, f"{label} · {args.dataset}", baseline), encoding="utf-8")
        if args.observations:
            args.observations.parent.mkdir(parents=True, exist_ok=True)
            metadata = {"mode": "synthetic" if args.offline else "live", "dataset": args.dataset}
            args.observations.write_text(
                "".join(json.dumps({**metadata, **asdict(r)}) + "\n" for r in rows), encoding="utf-8"
            )
        print(f"{label}: {len(rows)} observations → {args.output}")
        return int(any(r.error for r in rows))
    except (OSError, ValueError) as exc:
        print(f"Could not complete matrix: {exc}", file=sys.stderr)
        return 2


if __name__ == "__main__":
    raise SystemExit(matrix_main())
