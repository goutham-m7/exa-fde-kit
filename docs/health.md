# Customer health: a triage queue, not a churn model

    uv run python -m exa_fde_kit.health generate --end 2026-11-19 > synthetic-tenants.jsonl
    uv run python -m exa_fde_kit.health score synthetic-tenants.jsonl --end 2026-11-19 --mode synthetic

The fixture is **entirely synthetic**. Choose the last *complete* day in the customer's logs. Compare that day and the previous six UTC days with the preceding seven; each tenant is its own baseline. Mixed traffic is filtered by mode; real reports default to live. Combine each worker's append-only log exactly once. An outage in your log collector can look like churn.

* **Activity:** one completed query span is one query, even with retries, a cache hit, or a failed answer. Count distinct completion dates. Trend = (current − previous)/previous; a missing denominator is null, not zero.
* **Reliability:** failed attempts / outbound attempts; the 429 subset uses the same denominator. End-to-end p95 is nearest-rank query duration including backoff, not provider-attempt p95. Drift is relative to last week's p95.
* **Quality:** (blank + unsupported) / (blank + unsupported + supported). Nonblank citations are unassessed until adjudicated. Provider errors are not counted as quality judgments. Always inspect the assessment denominator: biased sampling can dominate this ratio.

Start at 100. Deduct 30 for a ≥40% volume decline (previous ≥5 queries), 20 for activity falling from ≥3 days to ≤1, 20 for ≥10% failed attempts (≥5 attempts; mention 429s rather than double counting), 25 for ≥25% bad assessed answers (≥5 assessed), and 15 for ≥50% p95 drift (both weeks ≥5 queries). Floor at zero; flag ≤70. With fewer than five queries in both windows, return unknown rather than a reassuring score. These thresholds are illustrative, not calibrated probabilities. Previous-only tenants are retained; tenants absent from both windows need an external account roster.

## How an FDE would use this with a customer

Use a pseudonymous team ID with `ask --tenant team-a` and [structured call logs](telemetry.md). In an embedding, wrap the search and final outcome in `with query_trace("team-a"):`, and call `record_answer(answer, client.mode, supported=review_result)` once, using an independently measured boolean or None. Do not infer health from historical untagged HTTP logs: retries aren't queries and a 200 isn't an accepted answer. Verify a flagged decline against the customer's workflow, holiday calendar and telemetry coverage before changing quota or escalating to account owners.
