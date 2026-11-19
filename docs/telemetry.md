# From call logs to request metrics

    uv run exa-fde-kit ask --offline --tenant pilot-a --case pg-index --log-calls 2>calls.jsonl
    uv run exa-fde-kit metrics calls.jsonl

The second command only reads the local file. A call span records endpoint, UTC completion timestamp, attempt, HTTP status or redacted failure class, elapsed milliseconds, cost basis, cached flag and random span/trace IDs. A query trace groups the Search and Contents attempts under one pseudonymous tenant and emits one answer completion. Never use a person's name, email, key, or query as the tenant slug. Embedders should route the kit's INFO logger to a dedicated JSONL sink; a CLI error message on stderr isn't a JSON event. Malformed JSON fails with a line number, not the row contents.

**Semantics.** Request, error, and HTTP 429 counts and latency histogram include each outbound attempt (including retries); cache hits have their own counter. Histogram boundaries are inclusive and cumulative in seconds, and exclude time waiting for admission or backoff. Cost is a subtotal of known or estimated amounts, not an invoice. Unknown charges are counted separately. Synthetic cost series are estimates of a hypothetical live run: actual spend is zero. The exporter keeps one fixed-size accumulator per bounded mode and endpoint, regardless of file length. It emits a snapshot, not a running HTTP scraper; do not sum repeated exports of the same growing log.

## How an FDE would use this with a customer

Slice by endpoint to distinguish slow contents reads from a search quota problem. Compare the attempt histogram with the answer's end-to-end latency. If attempts stay fast and answers slow down, examine admission and Retry-After rather than changing search settings. For account trends use the [tenant health report](health.md); logs classify an unjudged cited answer as unassessed, never as automatically supported.
