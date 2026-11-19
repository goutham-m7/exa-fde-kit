# exa-fde-kit · Developer support research desk

A support engineer asks, “How do we build a PostgreSQL index without blocking writes?” The agent returns a short passage with its source, or says it has no usable evidence. A second command checks whether retrieval found the right documentation **and** whether the cited passage contains the expected fact. A correct domain alone is not a correct answer.

Run the research desk offline without credentials, or compare retrieval policies against the live API. **Replay and live evidence are separate:** the checked-in replay contains original, invented passages and rankings; it is not a recording of Exa. No LLM key is needed for retrieval, routing or the benchmark.

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
# Paid comparison: 24 cases × 6 fixed settings, up to 288 requests before retries.
uv run exa-fde-kit eval --output reports/live.md
```

The benchmark is serial with the client cache disabled. With the rates below, all six fixed settings model **$1.344** for 24 questions each. The two-stage router adds up to **$0.408** per 24 questions at its defaults, before unexpected charges. These are planning figures, **not spending caps or quotes**. Check pricing, trial limits and your budget before running. Exit codes: 0 completed (possibly a no-evidence abstention); 1 provider/replay error; 2 missing configuration, invalid input or local I/O failure.

### Run the cascade and paired matrix

```bash
uv run exa-fde-kit ask --offline --case pg-index --preset router --router-usd .017 --router-ms 8000
uv run python -m exa_fde_kit.evaluation --offline --presets lite,summary,router \
  --repeat 2 --output reports/replay.html --observations reports/replay.jsonl
# Combine compatible JSONL runs later without paying again; fails on missing pairs.
uv run python -m exa_fde_kit.report_html reports/replay.jsonl --baseline lite --output reports/paired.html
uv run python -m exa_fde_kit.judge  # synthetic agreement; no calls

# Paid APJ smoke. --live is required; APJ has verified labels but no replay cassette.
uv run python -m exa_fde_kit.evaluation --live --dataset apj --presets lite,summary,router \
  --limit 2 --output reports/apj-smoke.html
```

Omit `--presets` for the six fixed presets plus the router. Set `--baseline lite` to choose the reference for paired intervals. `--repeat N --wait-seconds S` runs N complete windows with an S-second pause **between** windows. Repeats make fresh calls: cost grows with N. The HTML is a standalone, script-free file: recall, supported-answer rate, latency percentiles, spend per supported answer, paired CIs and error counts. Optional JSONL stores metrics per case/preset/window, not returned pages.

**What the cascade can see:** lite search and query-focused highlights, never the expected site or answer. Blank evidence, poor query overlap, or no second URL corroborating non-query terms can trigger auto search plus summaries. Both stages count toward cost and latency. A failed upgrade preserves usable initial evidence and exposes the error. `--router-usd` reserves the next stage's modeled list price, and `--router-ms` gates admission between stages. Neither can cancel an already billed or in-flight operation. Corroborating URLs can be mirrors; shared words do not establish independent factual agreement.

**Two checks, two questions.** The benchmark's original proxy asks whether an expected fact alias appears in a citation on an expected domain. The separate claim judge asks whether *each sentence* in a claim has support in the passages specifically cited for that claim. It checks lexical coverage, numeric tokens and negation within individual evidence sentences. It cannot establish real-world truth, and checking an extractive quote against itself says little about relevance. To judge generated answers, pass each claim and its associated passages to `LexicalJudge.supports(Claim(...))`; don't pool the whole retrieval result.

On [30 synthetic, author-labeled examples](src/exa_fde_kit/data/agreement.json) (15 supported, 15 unsupported), the fact-string judge agreed on **18/30** (12 false positives); the lexical judge on **24/30** (3 false positives, 3 false negatives). The stronger judge still accepts subject/object swaps and rejects genuine paraphrases. These examples were written during development, not independently annotated or held out. `python -m exa_fde_kit.judge --model` opts in to a paid [OpenAI model check](https://platform.openai.com/docs/api-reference/chat/create) on these examples only. It skips when `OPENAI_API_KEY` is absent; `OPENAI_JUDGE_MODEL` can override the model. No live model-judge accuracy or cost is claimed.

The [APJ label file](src/exa_fde_kit/data/apj.json) includes the query language, expected domain, acceptable answer strings, verification URL, the fact checked there, and date. Queries cover AWS regions, IANA domain registries and time-zone IDs, and Unicode CLDR currency codes. Each label was checked by fetching its official source; a source being correct does not guarantee that Exa will retrieve it. There are 3–4 cases per language, English included, and multiple questions target the same official tables. This is a narrow technical lookup set, **not** a general multilingual ability benchmark.

## Live results · 19 Nov 2026

**For these lookup tasks, try lite search + summaries before adding a router.** In the first pass it produced 17/24 supported English answers and 14/24 APJ answers at $0.007/query. The cascade produced 12/24 on both, at $0.00825 and $0.01450/query respectively. Plain lite had the lowest tail latency. These are observations on this corpus, not a provider-wide ranking.

**Measured:** 480 cold-client-cache query/policy trials, 1,014 HTTP requests, **$4.4460** in provider-reported cost, zero unknown charges. English matrix $1.5420; APJ matrix $1.6920; two English repeats $0.6060 each. No earlier pilot, speculative invoice discounts, or other integrations are included. The [observation files and self-contained charts](examples/benchmark-2026-11-19/) preserve UTC times, counts and charges without credentials or returned page text. Download an HTML file and open it locally to view its SVG charts.

**English · 24 developer-support questions, first pass.** Δ is *router minus that fixed preset*, in percentage points of supported-answer rate; brackets are the paired 95% interval. Disagreement on the *same cases* determines interval width.

| Policy | Recall@k | Supported | p50 / p95 (s) | USD / query | USD / supported answer | Router Δ [95% CI], pp |
|---|---:|---:|---:|---:|---:|---:|
| baseline | 87.5% | 11/24 | 0.70 / 3.38 | .010 | .0218 | +4.2 [−8.3, +16.7] |
| lite | 91.7% | 10/24 | 0.74 / 1.45 | .007 | .0168 | +8.3 [0.0, +20.8] |
| wide | 91.7% | 10/24 | 2.13 / 3.68 | .012 | .0288 | +8.3 [−8.3, +25.0] |
| summary | 87.5% | 16/24 | 4.01 / 5.42 | .010 | .0150 | −16.7 [−41.7, +8.3] |
| recent | 35.4% | 3/24 | 2.19 / 3.65 | .010 | .0800 | +37.5 [+20.8, +58.3] |
| lite-summary | 91.7% | 17/24 | 2.77 / 4.63 | .007 | .0099 | −20.8 [−41.7, 0.0] |
| router | 91.7% | 12/24 | 0.66 / 3.04 | .00825 | .0165 | reference |

**APJ · 24 multilingual technical lookups, first pass.** English routing escalated **3/24 (12.5%)** on low agreement. APJ routed **18/24 (75%)** onward: 12 low-agreement and 6 no-support decisions. Its p95 rose to 4.79 s (lite: 0.95 s). Query-to-passage overlap can be weak across writing systems even when retrieval found the right site. Escalation often helped relative to lite, but was more expensive than directly requesting summaries.

| Policy | Recall@k | Supported | USD / query | USD / supported answer | Router Δ [95% CI], pp |
|---|---:|---:|---:|---:|---:|
| baseline | 91.7% | 4/24 | .010 | .0600 | +33.3 [+8.3, +58.3] |
| lite | 87.5% | 3/24 | .007 | .0560 | +37.5 [+16.7, +58.3] |
| wide | 95.8% | 3/24 | .012 | .0960 | +37.5 [+12.5, +62.5] |
| summary | 91.7% | 15/24 | .010 | .0160 | −12.5 [−41.7, +16.7] |
| recent | 41.7% | 1/24 | .010 | .2400 | +45.8 [+25.0, +66.7] |
| lite-summary | 87.5% | 14/24 | .007 | .0120 | −8.3 [−33.3, +12.5] |
| router | 91.7% | 12/24 | .01450 | .0290 | reference |

APJ breakdown (router vs auto-summary): Japanese **2 vs 3** of 4; Korean **1 vs 2** of 4; Hindi **2 vs 4** of 4; Indonesian **3 vs 1** of 3; Simplified Chinese **0 vs 2** of 3; Vietnamese **2 vs 1** of 3; English on APJ topics **2 vs 2** of 3. These are drilldowns, not evidence that one language is intrinsically harder. Requiring one canonical domain can penalize a factually correct alternate source.

**Two additional paid English passes.** On all 24 cases: lite supported 10 → 10 → 10; summary 16 → 17 → 18; router 12 → 12 → 12. Over the three passes, auto-summary minus lite was **+29.2 pp [8.3, 50.0]** for $0.003 more per query and +2.38 s mean latency [2.11, 2.64]. Router minus lite was **+8.3 pp [0.0, 20.8]**, at +$0.00125/query and +0.24 s mean latency [−0.04, +0.59]. The 72 query runs per policy are **24 cases**, not 72 independent samples.

**How to interpret the uncertainty:** resample the 24 paired case differences 4,000 times with seed 42. For repeats, average each case's differences across passes before resampling cases. These are marginal percentile intervals with no correction for multiple comparisons. The collection spanned 05:58–06:16 UTC on one day. In English the initial lite/summary smoke and fixed matrix preceded the router; for repeats the first 20 cases were run twice, then the final four twice after checking funds. Pass IDs are per-case repetitions, not strictly disjoint calendar windows. Provider caching, network conditions and shared source pages can correlate outcomes. Re-run across days, locations and real held-out questions before setting an SLO. “Supported” is the domain + fact proxy, not independent human verification of an Exa summary.

To regenerate the repeat chart from the receipts (no API key):

```bash
cd examples/benchmark-2026-11-19
uv run --project ../.. python -m exa_fde_kit.report_html english.jsonl english-repeats.jsonl \
  --presets lite,summary,router --baseline lite --output /tmp/three-passes.html
```

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
| lite-summary | lite search followed by a separate summary contents request | Can a cheaper first stage retain the quality of summaries? |

For each case, preset order is shuffled with seed 42. Look at the same case across presets, not just the mean.

- **Domain recall@k** = expected domains found in the first k search hits / expected domains, macro-averaged over cases. Hostname or actual subdomain matches; lookalikes don't. Finding two pages on one expected site still counts once.
- **Supported cites** = cited passages on an expected domain containing a labeled fact alias / emitted citations. **Supported answers** = cases with at least one supported citation / all cases, including blanks and errors. This lexical proxy can accept negation and reject paraphrases. It does **not** verify a generated summary against the original page. Review false positives as well as the report's unsupported-answer drilldown; record human accuracy separately.
- **Latency:** end-to-end nearest-rank p50/p95 per preset, including retries and failed runs. Offline values time the local fixture machinery only. With just 24 cases, the p95 is one tail observation; repeat a live comparison across time windows and from the customer's deployment region.
- **Cost:** use `costDollars.total` if provided; otherwise model successful searches at $0.007 (auto) or $0.004 (lite) and one requested content view at $0.001 per requested page. Cache hits cost zero; failed/uncertain attempts have unknown cost, counted separately. A subtotal with unknowns is not the bill. Source: [Exa pricing](https://docs.exa.ai/admin/pricing.md), checked 2026-11-18. Replace these assumptions for contracted pricing; reconcile real spend with billing.

## Customer integrations and operations

- [MCP over stdio](docs/mcp.md): read-only retrieval tools and a key-free replay mode.
- [Websets monitor](docs/monitor.md): a daily funding-news inbox and signed event receiver.
- [Load harness](docs/loadtest.md): exercise request pacing and shared cooldowns without paid traffic.
- [Telemetry](docs/telemetry.md) and [customer health](docs/health.md): correlate calls with answers, export metrics, and triage account changes without passing raw user questions into logs.

## Contract → production playbook

| Stage | Deliverable and decision |
|---|---|
| Contract handoff | With the support lead and engineering owner, agree on the ticket category, excluded data, target region, budget per resolved ticket, acceptable timeout and rollback owner. Obtain a redacted sample with permission; measure current resolution time and escalation rate **before** the pilot. |
| First integration | Start with two non-sensitive questions. Verify network/auth, both endpoints, source links and an intentional no-evidence path. Demonstrate one surprising miss. Agree which failures require a human, and what constitutes a supported resolution. |
| Offline and shadow eval | Have subject experts label representative held-out cases, including “no valid source.” Keep test accounts and training questions separate. Run paired live configs plus the customer's incumbent on the same set; inspect the worst regressions, not just average recall. Check actual invoice data against estimates. |
| Canary | Route a small, reversible slice to read-only suggestions. Keep the incumbent path. Compare support-agent acceptance, reopens, human-judged factuality, p95 and cost per accepted answer. Agree thresholds **with the customer**; roll back on harmful answers, privacy leakage or budget/SLO breaches. |
| Operation and handoff | Name an on-call owner, rotate credentials in a secret store, cap spend and request rate per tenant, enforce an application deadline, set retention, and document the kill switch. Review retrieval/contents failure patterns weekly, refresh the golden set from adjudicated misses, and record the decision to expand or hold. |

**Churn review:** Compare cohorts against their own pilot baseline. Falling weekly returning agents or decreasing suggested-answer acceptance can signal the tool is being bypassed; interview the desk lead and inspect rejected evidence. Rising retries, p95, abandonment or 429s point to a poor interaction loop; separate search from contents before changing either. Track confirmed resolutions per active team and spend per accepted resolution: rising call volume alone can mean the product is forcing repeat searches. A useful weekly review pairs one trend with one rejected ticket, one owner and a dated corrective action. Product/adoption measures require events from the customer's app; this CLI does not pretend to collect them.

MIT licensed. The replay and judge fixtures are synthetic; APJ source labels and the separately marked live measurement receipts are not.
