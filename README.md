# exa-fde-kit · Developer support research desk

A support engineer asks, “How do we build a PostgreSQL index without blocking writes?” The agent returns a short passage with its source, or says it has no usable evidence. A second command checks whether retrieval found the right documentation **and** whether the cited passage contains the expected fact. A correct domain alone is not a correct answer.

**No live Exa result is claimed here.** The checked-in cassette contains hand-written text, invented publication dates and fixed rankings. Its URLs identify example source pages; its passages are not quotations from those pages. Real quality, latency and cost numbers come from running with your own key. No LLM key is required.

## Try it without a key

From the project root, with [uv](https://docs.astral.sh/uv/) installed:


```bash
uv sync --locked
uv run pytest
uv run exa-fde-kit ask --offline --case pg-index --log-calls
uv run exa-fde-kit eval --offline
```

The first sync may download Python and dependencies. After that, `uv --offline run pytest` also prevents the package manager from using the network. The CLI's separate `--offline` flag selects the local HTTP replay transport and never reads a key or falls back to the API. Offline questions must match a recording; `ask --help` lists case IDs.

The demo answer above selects **CREATE INDEX CONCURRENTLY** and cites the corresponding PostgreSQL documentation URL. That is synthetic evidence, not a live lookup. The full run writes `reports/synthetic.md`; [this checked-in example](examples/synthetic-report.md) shows the report without installing anything. For the baseline in that replay, every expected domain was found, but only 19/24 answers contained a matching fact on an expected domain. That gap is useful for testing the scorer, **not** for choosing a search provider or preset.

## Run it live, in order

Supply an authorized, funded key as `EXA_API_KEY` via your secret manager or shell environment. Don't put it in source, a URL, a command argument, or a ticket. You'll need outbound HTTPS to `api.exa.ai`. Authentication and endpoint contracts: [official SDK quickstart](https://docs.exa.ai/sdks/quickstart.md), [Search](https://docs.exa.ai/search/quickstart.md), [Contents](https://docs.exa.ai/contents/quickstart.md), all checked 2026-11-18.


```bash
# One customer-style question; bypass the local disk cache for this smoke test.
uv run exa-fde-kit ask --no-cache 'How does pip enforce hashes for all requirements?'
# Paid smoke: two questions, one preset. Inspect evidence and errors first.
uv run exa-fde-kit eval --limit 2 --preset baseline --output reports/live-smoke.md
# Paid comparison: 24 cases × 5 settings, up to 240 requests before retries.
uv run exa-fde-kit eval --output reports/live.md
```

The benchmark is serial with cache disabled. At the documented rates used by this estimator, the full matrix with all requested pages and no retries models about **$1.18**. This is a planning figure, **not a spending cap or quote**. Check contract pricing, trial limits and your budget before running. Exit codes: 0 completed (possibly a genuine no-evidence abstention); 1 provider/replay error (eval still writes the report); 2 missing configuration, invalid input or local I/O failure.

## Use it as a tool in a customer's agent

Call this from the server-side tool handler. Reuse one client per credential so workers share its connection pool and concurrency gate. The host agent should display the exact evidence and URLs, never let a passage select a tool, and hand an empty result to a human. The code below deliberately disables local persistence.


```python
import os
import httpx
from exa_fde_kit.agent import research
from exa_fde_kit.client import Client

with httpx.Client(base_url="https://api.exa.ai", timeout=httpx.Timeout(15, connect=4),
                  headers={"x-api-key": os.environ["EXA_API_KEY"]}) as http:
    tool = Client(http, concurrency=4)
    answer = research(tool, "Which Kubernetes probe controls readiness for traffic?")
    evidence = [{"passage": c.text, "url": c.url} for c in answer.citations]
    # answer.error is a redacted diagnostic; an empty evidence list is not a successful answer.
```

- **Retrieval:** `POST /search` finds URLs; one batched `POST /contents` requests query-focused highlights or summaries. Only known input IDs and valid HTTP(S) source links can become citations. The best overlapping query terms select passages; ties preserve search order. Summary mode labels generated summaries rather than presenting them as direct quotes. This is an evidence baseline, not a general reasoning engine. See [design and SDK tradeoff](DESIGN.md) and the [wire schemas](https://docs.exa.ai/reference/get-contents.md) (2026-11-18).
- **Load/failure:** at most four simultaneous HTTP attempts per client by default. 4 s connect, 15 s I/O timeouts, not a whole-answer wall-clock deadline. Retry 429 and 5xx up to three attempts with exponential full jitter; release the concurrency slot during backoff. Honor Retry-After (seconds or HTTP date); if the server asks for over 10 s, return the error instead of retrying early. Do not retry other 4xx or ambiguous transport failures.
- **Privacy/cache:** live `ask` caches responses in `$XDG_CACHE_HOME/exa-fde-kit/responses.sqlite3` (default `~/.cache` base). One-hour TTL; expired rows pruned on next initialization. Keys hash the credential namespace, endpoint and request; values contain unencrypted returned material. Use `--no-cache` for sensitive traffic; don't share the file between tenants. The demo is for public developer docs, not private tickets. Eval reports contain source evidence: restrict access before using a customer dataset.
- **Observability:** live CLI writes one JSON event to stderr per HTTP attempt or cache hit; enable `--log-calls` to see the same in replay. Includes mode, endpoint, attempt, status, latency_ms, cached, usd and cost_basis. No raw queries, URLs, passages or keys in **call logs**. Answers/reports intentionally contain evidence. Use your app's logger configuration for the `exa_fde_kit` logger when embedding.

## Reading the report

The [24-case label set](src/exa_fde_kit/data/cases.json) covers runtime, containers, databases, tooling and browser support. Each case has expected domains and one fact with accepted aliases. The evaluator, not the agent, reads these labels to score an answer. [Synthetic recordings](src/exa_fde_kit/data/synthetic.json) have a separate fixed result ordering per query/search type and both content views. The HTTP replay applies the requested count and publication cutoff to the cassette. It does not simulate Exa's ranking, billing or speed.

| Preset | Change from baseline | Customer question |
|---|---|---|
| baseline | auto search, 3 results, highlights, no date cutoff | Is a small evidence set enough? |
| lite | search type only | Does a cheaper retrieval path preserve usefulness? |
| wide | 5 results instead of 3 | Does the added context recover missing evidence? |
| summary | summaries instead of highlights | Are generated summaries more usable without losing facts? |
| recent | publication on/after 2024-01-01 | Do we exclude useful evergreen documentation? |

For each case, preset order is shuffled with seed 42. Look at the same case across presets, not just the mean.

- **Domain recall@k** = expected domains found in the first k search hits / expected domains, macro-averaged over cases. Hostname or actual subdomain matches; lookalikes don't. Finding two pages on one expected site still counts once.
- **Supported cites** = cited passages on an expected domain containing a labeled fact alias / emitted citations. **Supported answers** = cases with at least one supported citation / all cases, including blanks and errors. This lexical proxy can accept negation and reject paraphrases. It does **not** verify a generated summary against the original page. Review false positives as well as the report's unsupported-answer drilldown; record human accuracy separately.
- **Latency:** end-to-end nearest-rank p50/p95 per preset, including retries and failed runs. Offline values time the local fixture machinery only. With just 24 cases, the p95 is one tail observation; repeat a live comparison across time windows and from the customer's deployment region.
- **Cost:** use `costDollars.total` if provided; otherwise model successful searches at $0.007 (auto) or $0.004 (lite) and one requested content view at $0.001 per requested page. Cache hits cost zero; failed/uncertain attempts have unknown cost, counted separately. A subtotal with unknowns is not the bill. Source: [Exa pricing](https://docs.exa.ai/admin/pricing.md), checked 2026-11-18. Replace these assumptions for contracted pricing; reconcile real spend with billing.

## Contract → production playbook

| Stage | Deliverable and decision |
|---|---|
| Contract handoff | With the support lead and engineering owner, agree on the ticket category, excluded data, target region, budget per resolved ticket, acceptable timeout and rollback owner. Obtain a redacted sample with permission; measure current resolution time and escalation rate **before** the pilot. |
| First integration | Start with two non-sensitive questions. Verify network/auth, both endpoints, source links and an intentional no-evidence path. Demonstrate one surprising miss. Agree which failures require a human, and what constitutes a supported resolution. |
| Offline and shadow eval | Have subject experts label representative held-out cases, including “no valid source.” Keep test accounts and training questions separate. Run paired live configs plus the customer's incumbent on the same set; inspect the worst regressions, not just average recall. Check actual invoice data against estimates. |
| Canary | Route a small, reversible slice to read-only suggestions. Keep the incumbent path. Compare support-agent acceptance, reopens, human-judged factuality, p95 and cost per accepted answer. Agree thresholds **with the customer**; roll back on harmful answers, privacy leakage or budget/SLO breaches. |
| Operation and handoff | Name an on-call owner, rotate credentials in a secret store, cap spend and request rate per tenant, enforce an application deadline, set retention, and document the kill switch. Review retrieval/contents failure patterns weekly, refresh the golden set from adjudicated misses, and record the decision to expand or hold. |

**Churn review:** Compare cohorts against their own pilot baseline. Falling weekly returning agents or decreasing suggested-answer acceptance can signal the tool is being bypassed; interview the desk lead and inspect rejected evidence. Rising retries, p95, abandonment or 429s point to a poor interaction loop; separate search from contents before changing either. Track confirmed resolutions per active team and spend per accepted resolution: rising call volume alone can mean the product is forcing repeat searches. A useful weekly review pairs one trend with one rejected ticket, one owner and a dated corrective action. Product/adoption measures require events from the customer's app; this CLI does not pretend to collect them.

MIT licensed. All sample questions and fixtures are original, synthetic material.
