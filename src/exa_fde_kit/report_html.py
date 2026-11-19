"""Self-contained, script-free charts. Inline text equivalents keep the results accessible."""

from __future__ import annotations

import argparse
import json
from dataclasses import fields
from pathlib import Path

from collections.abc import Sequence
from html import escape
from statistics import fmean

from .stats import Effect, Observation, paired_effect, percentile


def _bars(title: str, unit: str, values: dict[str, float | None]) -> str:
    largest = max((v for v in values.values() if v is not None), default=0) or 1
    parts = [
        f'<figure><figcaption>{title}</figcaption><svg xmlns="http://www.w3.org/2000/svg" role="img" aria-label="{title}" viewBox="0 0 640 {32 * len(values) + 10}"><title>{title}</title>'
    ]
    precision = 4 if unit == " USD" else 1
    for n, (name, val) in enumerate(values.items()):
        y = 24 + n * 32
        label = "n/a" if val is None else f"{val:.{precision}f}{unit}"
        width = (val or 0) / largest * 360
        parts.append(
            f'<text x="8" y="{y}">{escape(name)}</text><rect x="126" y="{y - 13}" width="{width:.1f}" height="14" fill="#087e76"/><text x="{134 + width:.1f}" y="{y}">{label}</text>'
        )
    return "".join(parts) + "</svg></figure>"


def _intervals(effects: dict[str, Effect], baseline: str) -> str:
    title = (
        "Supported-answer difference vs " + escape(baseline) + " (percentage points; paired 95% CI)"
    )
    parts = [
        f'<figure><figcaption>{title}</figcaption><svg xmlns="http://www.w3.org/2000/svg" role="img" aria-label="{title}" viewBox="0 0 820 {max(52, 32 * len(effects) + 12)}"><title>{title}</title>',
        f'<path d="M 300 0 v {32 * len(effects)}" stroke="#777" stroke-dasharray="4"/>',
    ]
    if not effects:
        parts.append('<text x="10" y="26">Choose two or more presets for paired effects.</text>')
    for i, (name, e) in enumerate(effects.items()):
        y = i * 32 + 20
        parts.append(
            f'<text x="8" y="{y + 5}">{escape(name)}</text><line x1="{300 + 160 * e.low:.1f}" x2="{300 + 160 * e.high:.1f}" y1="{y}" y2="{y}" stroke="#305781" stroke-width="4"/><circle cx="{300 + 160 * e.estimate:.1f}" cy="{y}" r="5" fill="#182944"/><text x="485" y="{y + 5}">{100 * e.estimate:+.1f} [{100 * e.low:+.1f}, {100 * e.high:+.1f}] pp</text>'
        )
    return "".join(parts) + "</svg></figure>"


def render(rows: Sequence[Observation], label: str, baseline: str) -> str:
    if not rows or baseline not in {r.preset for r in rows}:
        raise ValueError("report needs observations for the baseline")
    names = list(dict.fromkeys(r.preset for r in rows))
    groups = {name: [r for r in rows if r.preset == name] for name in names}
    effects = {name: paired_effect(rows, name, baseline) for name in names if name != baseline}
    cost = {}
    for name, group in groups.items():
        count = sum(r.supported for r in group)
        cost[name] = (
            sum(r.usd for r in group) / count
            if count and not any(r.unknown_costs for r in group)
            else None
        )
    panels = [
        _bars(
            "Expected-domain recall@k",
            "%",
            {n: 100 * fmean(r.recall for r in g) for n, g in groups.items()},
        ),
        _bars(
            "Supported answers",
            "%",
            {n: 100 * fmean(r.supported for r in g) for n, g in groups.items()},
        ),
        *[
            _bars(
                f"End-to-end p{p} latency",
                " ms",
                {n: percentile([r.latency_ms for r in g], p / 100) for n, g in groups.items()},
            )
            for p in (50, 95)
        ],
        _bars("Cost per supported answer", " USD", cost),
        _intervals(effects, baseline),
    ]
    audit = "".join(
        f"<tr><th>{escape(n)}</th><td>{len(g)}</td><td>{sum(r.supported for r in g)}</td><td>{sum(r.escalated for r in g)}/{len(g)}</td><td>{sum(r.error for r in g)}</td><td>{sum(r.blank for r in g)}</td><td>{sum(r.usd for r in g):.4f}</td><td>{sum(r.unknown_costs for r in g)}</td></tr>"
        for n, g in groups.items()
    )
    windows = ", ".join(escape(w) for w in sorted({r.window for r in rows}))
    return (
        f'<!doctype html><html lang="en"><meta charset="utf-8"><meta name="viewport" content="width=device-width, initial-scale=1"><title>{escape(label)}</title>'
        "<style>body{max-width:58rem;margin:2rem auto;padding:0 1rem;font:16px/1.5 system-ui;color:#192e36}figure{margin:1.3rem 0;padding:1rem;background:#eff5f5}figcaption,th{font-weight:650}svg{width:100%;height:auto}svg text{font:15px system-ui;fill:#18252c}table{border-collapse:collapse;width:100%}th,td{text-align:left;padding:.4em;border-bottom:1px solid #ccc}.table{overflow:auto}</style>"
        f"<main><h1>{escape(label)}</h1><p>Windows: {windows}. Labels test source domain and fact alias, not logical entailment. Blanks and errors remain in the denominator.</p>"
        f"<p>Known/estimated cost of these observations: ${sum(r.usd for r in rows):.4f}; "
        f"{sum(r.unknown_costs for r in rows)} attempts with unknown charges.</p>"
        + "".join(panels)
        + '<h2>Audit totals</h2><div class="table"><table><tr><th>Preset</th><th>Runs</th><th>Supported</th><th>Escalations</th><th>Errors</th><th>Blanks</th><th>Known/est. USD</th><th>Unknown charges</th></tr>'
        + audit
        + "</table></div>"
        "<p>Nearest-rank latency. Cost per success is n/a for zero successes or unknown charges. CIs: percentile bootstrap of 4,000 paired case resamples, seed 42; average windows within each case first. These intervals do not estimate between-day or deployment-region variance.</p></main></html>"
    )


def merge_reports(paths: Sequence[Path], baseline: str, presets: set[str] | None = None) -> str:
    """Rebuild one report from cold-run JSONL files; never contact a provider."""
    rows: list[Observation] = []
    provenance: set[tuple[str, str]] = set()
    seen: set[tuple[str, str, str]] = set()
    keys = [f.name for f in fields(Observation)]
    for path in paths:
        with path.open(encoding="utf-8") as stream:
            for line, raw in enumerate(stream, 1):
                try:
                    record = json.loads(raw)
                    dataset, mode = record["dataset"], record["mode"]
                    if not isinstance(dataset, str) or mode not in ("live", "synthetic"):
                        raise ValueError("invalid dataset/mode")
                    row = Observation(**{k: record[k] for k in keys})
                except (KeyError, ValueError, TypeError) as exc:
                    raise ValueError(f"{path}:{line}: invalid observation") from exc
                provenance.add((dataset, mode))
                if presets is not None and row.preset not in presets:
                    continue
                key = (row.window, row.preset, row.case)
                if key in seen:
                    raise ValueError(f"{path}:{line}: duplicate case/preset/window")
                seen.add(key)
                rows.append(row)
    if len(provenance) != 1:
        raise ValueError("observations must share the same dataset and mode")
    if presets is not None and {r.preset for r in rows} != presets:
        raise ValueError("a selected preset has no observations")
    dataset, mode = provenance.pop()
    label = "LIVE API" if mode == "live" else "SYNTHETIC REPLAY (not Exa latency; actual spend $0)"
    return render(rows, f"{label} · {dataset}", baseline)


def main() -> None:
    parser = argparse.ArgumentParser(
        description="Aggregate saved matrix observations without API calls"
    )
    parser.add_argument("inputs", type=Path, nargs="+")
    parser.add_argument("--presets", help="comma-separated common presets for unequal-sized runs")
    parser.add_argument("--baseline", required=True)
    parser.add_argument("--output", type=Path, required=True)
    args = parser.parse_args()
    if args.output.resolve() in {path.resolve() for path in args.inputs}:
        parser.error("output must not overwrite an input")
    try:
        presets = {p.strip() for p in args.presets.split(",")} if args.presets else None
        page = merge_reports(args.inputs, args.baseline, presets)
        args.output.parent.mkdir(parents=True, exist_ok=True)
        args.output.write_text(page, encoding="utf-8")
    except (OSError, ValueError) as exc:
        parser.exit(2, f"Cannot build report: {exc}\n")


if __name__ == "__main__":
    main()
