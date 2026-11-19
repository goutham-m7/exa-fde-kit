"""Paired, cold-cache benchmark with independent domain and evidence labels."""

from __future__ import annotations

from dataclasses import dataclass
from datetime import datetime, timezone
from html import escape
from importlib.resources import files
import json
import math
import random
import re
from statistics import mean
from urllib.parse import urlsplit

from .agent import Answer, Config, research
from .client import Client

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


def load_cases() -> list[Case]:
    data = files(__package__).joinpath("data/cases.json").read_bytes()
    return [Case(**row) for row in json.loads(data)]


def matches(url: str, domain: str) -> bool:
    host = (urlsplit(url).hostname or "").lower().rstrip(".")
    return host == domain or host.endswith("." + domain)


def score(case: Case, answer: Answer, k: int) -> tuple[float, int]:
    hits = sum(any(matches(url, d) for url in answer.urls[:k]) for d in case.domains)
    supported = sum(
        any(matches(c.url, d) for d in case.domains)
        and any(re.search(r"(?<!\w)" + re.escape(a) + r"(?!\w)", c.text, re.IGNORECASE) is not None
                for a in case.aliases)
        for c in answer.citations
    )
    return hits / len(case.domains), supported


def percentile(values: list[float], fraction: float) -> float:
    return sorted(values)[max(0, math.ceil(len(values) * fraction) - 1)]


@dataclass(frozen=True)
class Trial:
    name: str
    case: Case
    answer: Answer
    recall: float
    supported: int

    @property
    def known_usd(self):
        return sum(c.usd for c in self.answer.calls if c.usd is not None)


def evaluate(client: Client, cases: list[Case], names: list[str]) -> list[Trial]:
    if client.cache:
        raise ValueError("benchmark must not share cached responses")
    rng = random.Random(42)
    trials = []
    for case in cases:
        order = names.copy()
        rng.shuffle(order)
        for name in order:
            cfg = PRESETS[name]
            answer = research(client, case.question, cfg)
            trials.append(Trial(name, case, answer, *score(case, answer, cfg.k)))
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
        lines.append(f"| {name} | {len(rows)} | {PRESETS[name].k} | {mean(r.recall for r in rows):.1%} | "
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
