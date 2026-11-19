"""Paired case bootstrap; repeat windows are blocks, not extra independent cases."""

from __future__ import annotations

import math
import random
from collections import defaultdict
from collections.abc import Sequence
from dataclasses import dataclass
from statistics import fmean
from typing import Literal

Metric = Literal["supported", "recall", "usd", "latency_ms"]


@dataclass(frozen=True)
class Observation:
    case: str
    preset: str
    window: str
    recall: float
    supported: bool
    latency_ms: float
    usd: float  # Known or estimated subtotal. Never silently impute unknown charges.
    unknown_costs: int
    escalated: bool
    error: bool = False
    blank: bool = False

    def __post_init__(self) -> None:
        if not all(isinstance(s, str) and s.strip() for s in (self.case, self.preset, self.window)):
            raise ValueError("empty case, preset or window")
        if not all(
            type(v) is bool for v in (self.supported, self.escalated, self.error, self.blank)
        ):
            raise ValueError("outcomes must be booleans")
        if type(self.unknown_costs) is not int or self.unknown_costs < 0:
            raise ValueError("unknown charge count must be a non-negative integer")
        for v in (self.recall, self.latency_ms, self.usd):
            if type(v) not in (int, float) or not math.isfinite(v) or v < 0:
                raise ValueError("metrics must be finite and non-negative")
        if self.recall > 1:
            raise ValueError("recall must be in [0, 1]")


@dataclass(frozen=True)
class Effect:
    estimate: float
    low: float
    high: float
    cases: int
    windows: int


def percentile(values: Sequence[float], fraction: float) -> float:
    if not values or not 0 <= fraction <= 1:
        raise ValueError("percentile requires values and a fraction in [0, 1]")
    return sorted(values)[max(0, math.ceil(len(values) * fraction) - 1)]


def paired_effect(
    rows: Sequence[Observation],
    candidate: str,
    baseline: str,
    metric: Metric = "supported",
    *,
    samples: int = 4000,
    seed: int = 42,
) -> Effect:
    """Estimate mean(candidate − baseline). Reject missing, duplicate or ragged pairs."""
    if candidate == baseline or samples < 1:
        raise ValueError("use distinct presets and a positive sample count")
    by_preset: dict[str, dict[tuple[str, str], float]] = {candidate: {}, baseline: {}}
    for row in rows:
        if row.preset not in by_preset:
            continue
        if metric == "usd" and row.unknown_costs:
            raise ValueError("cannot estimate spend differences with unknown charges")
        key = (row.case, row.window)
        values = by_preset[row.preset]
        if key in values:
            raise ValueError(f"duplicate observation: {key}, {row.preset}")
        values[key] = float(getattr(row, metric))
    a, b = by_preset[candidate], by_preset[baseline]
    if not a or a.keys() != b.keys():
        raise ValueError("presets must have matching case/window pairs")
    windows = {w for _, w in a}
    grouped: dict[str, list[float]] = defaultdict(list)
    for key in sorted(a):
        grouped[key[0]].append(a[key] - b[key])
    if any(len(group) != len(windows) for group in grouped.values()):
        raise ValueError("each case must appear in every window")
    diffs = [fmean(group) for group in grouped.values()]
    n = len(diffs)
    rng = random.Random(seed)
    draws = sorted(fmean(rng.choices(diffs, k=n)) for _ in range(samples))
    return Effect(
        fmean(diffs),
        draws[math.ceil(samples * 0.025) - 1],
        draws[math.ceil(samples * 0.975) - 1],
        n,
        len(windows),
    )
