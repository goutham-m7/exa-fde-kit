"""Two-stage admission control. Never consult benchmark labels to choose a route."""

from __future__ import annotations

import math
from dataclasses import dataclass, replace
from time import monotonic

from .agent import Answer, Config, research, terms
from .client import Client, cost

_LITE = Config(search_type="lite")
_UPGRADE = Config(mode="summary")


def _reservation(config: Config) -> float:
    return (
        cost("search", {"type": config.search_type}, {})[0]
        + cost("contents", {"ids": range(config.k)}, {})[0]
    )


@dataclass(frozen=True)
class Budget:
    usd: float = 0.017
    latency_ms: float = 8000

    def __post_init__(self) -> None:
        if not all(math.isfinite(x) and x >= 0 for x in (self.usd, self.latency_ms)):
            raise ValueError("budgets must be finite and non-negative")


@dataclass(frozen=True)
class Route:
    answer: Answer
    escalated: bool
    reason: str
    selected: str


def _weakness(question: str, answer: Answer) -> str | None:
    if not answer.citations:
        return "blank"
    query = terms(question)
    first = answer.citations[0]
    words = terms(first.text)
    if not query or len(query & words) / len(query) < 0.2:
        return "no_support"
    # Compare non-question terms: echoing the question is not corroboration.
    detail = words - query
    for other in answer.passages:
        if other.url == first.url:
            continue
        second = terms(other.text) - query
        shared = detail & second
        if len(shared) >= 2 and len(shared) / min(len(detail), len(second)) >= 0.2:
            return None
    return "low_agreement"


def cascade(client: Client, question: str, budget: Budget = Budget()) -> Route:
    if not question.strip():
        raise ValueError("question must not be empty")
    start = monotonic()
    if budget.usd < _reservation(_LITE) or budget.latency_ms == 0:
        return Route(Answer(), False, "budget", "none")
    lite = research(client, question, _LITE)
    if lite.error or any(c.usd is None for c in lite.calls):
        return Route(lite, False, "provider_error", "lite")
    reason = _weakness(question, lite)
    if reason is None:
        return Route(lite, False, "corroborated", "lite")
    spent = sum(c.usd for c in lite.calls if c.usd is not None)
    if (
        spent + _reservation(_UPGRADE) > budget.usd + 1e-12
        or (monotonic() - start) * 1000 >= budget.latency_ms
    ):
        return Route(lite, False, "budget", "lite")
    upgrade = research(client, question, _UPGRADE)
    # A failed upgrade doesn't erase a usable first answer or hide the failure/cost.
    choose_upgrade = bool(upgrade.citations) or not lite.citations
    selected = upgrade if choose_upgrade else lite
    final = replace(
        selected,
        calls=lite.calls + upgrade.calls,
        elapsed_ms=(monotonic() - start) * 1000,
        error=upgrade.error or selected.error,
    )
    return Route(final, True, reason, "summary" if choose_upgrade else "lite")
