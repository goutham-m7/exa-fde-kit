# Decision: two-stage retrieval for a developer support desk

A platform support engineer needs a short, citation-backed answer before replying to a developer. A wrong answer is worse than an explicit lack of evidence. Build an extractive evidence agent, not an unconstrained chatbot: retrieve ranked URLs, request focused passages or generated summaries, and cite the passages that share the most terms with the question. Keep ties in retrieval order (up to three sources); when there is no overlap, use the first available passage. This cheap ranking signal is not a factuality check. No LLM key, autonomous browsing, or customer data is needed.

A single search with inline contents would usually save a round trip. Here separate stages let the team inspect misses, change extraction mode independently, and cache discovery separately. A generative synthesis step might improve readability but would require a second provider and a separate faithfulness evaluation. The baseline deliberately leaves that out.

## Boundary and failure behavior

CLI → agent → concurrency-limited HTTP client → search, then contents. The same HTTP client and parser run against a local synthetic replay transport. Gold labels belong to the scorer, never the agent. Cache only successful provider responses, private to one local operator, with a TTL. Disable caching for benchmarks. No key, query text, URLs or passages in call logs. Treat retrieved text as untrusted data; do not execute it. Skip missing/failed evidence; abstain when empty. Retry transient HTTP statuses with bounded jitter; do not automatically rebill ambiguous transport timeouts. Preserve failed cases in eval denominators. Expose partial or unknown cost rather than imputing zero.

Use HTTPX rather than wrapping the official SDK's errors: the inspected exa-py 2.28.0 non-streaming request path converts HTTP errors to ValueError with the response body, losing typed status and Retry-After headers. Direct HTTP preserves both. SDK and REST reference: [SDK quickstart](https://docs.exa.ai/sdks/quickstart.md), [search](https://docs.exa.ai/search/quickstart.md), [contents](https://docs.exa.ai/contents/quickstart.md), checked 2026-11-18. SDK implementation: [Python package v2.28.0](https://pypi.org/project/exa-py/2.28.0/), inspected 2026-11-18.

## Rollout and verification

Start with an offline fixture replay, then run a two-case paid smoke with a customer-approved key and budget. Expand to the paired query matrix before recommending a preset. Shadow customer traffic only after data review; canary the winning preset against the incumbent and retain a rollback switch upstream. Test the HTTP boundary, ranking, partial failures, independent scoring, replay isolation, and rendered report. Live performance and billing remain unverified until measured.
