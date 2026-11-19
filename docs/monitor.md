# A daily funding-news inbox

Use the [Websets monitor](https://docs.exa.ai/websets/api/monitors/create-a-monitor.md) product when the customer wants an accumulating, verified set of articles. The similarly named [Monitors API](https://docs.exa.ai/monitors/quickstart.md) sends whole run results and uses a different payload. This receiver is **only for Websets item-created events**.

## Configure without starting a paid schedule

Generate the request bodies locally:

    uv run python -m exa_fde_kit.monitor definition ws_example https://customer.example/webhook

Output contains two method/URL/body triples for an existing Webset: daily UTC article search and [webhook subscription](https://docs.exa.ai/websets/api/webhooks/create-a-webhook.md). The command does not submit them. Have the owner approve the recurring budget first. Register the webhook first at its final HTTPS URL; store its one-time signing secret in the deployment secret store, not the Exa API key. Exa sends events for the team, so the receiver must filter by Webset. Start the monitor last. To end a pilot delete the Websets monitor and webhook by their returned IDs; deleting local state does not stop billing.

    # Provide EXA_WEBHOOK_SECRET from your secret store.
    uv run python -m exa_fde_kit.monitor serve ws_example inbox.sqlite --port 8765
    uv run python -m exa_fde_kit.monitor digest ws_example inbox.sqlite 2026-11-19

The local HTTP server binds to loopback only. For hosted delivery use a TLS terminator with request limits; do not expose the stdlib development server directly. Verify [Exa-Signature](https://docs.exa.ai/websets/api/webhooks/verifying-signatures.md) on the raw body before decoding, reject timestamps more than five minutes away, then commit the event receipt and article together. Duplicate signed deliveries receive success without producing a second entry, even after restart. Times are UTC **event creation** dates, not publication dates. A late delivery can update a past day's digest. Retain the SQLite file and protect it as customer data. For multiple replicas use a shared transactional store, not one local file per worker.

## How an FDE would use this with a customer

Review one day's links with the analyst: are they original funding announcements, or syndicated copies? Deduplication recognizes item IDs, HTTP fragments, default ports and common tracking parameters, not different stories with similar wording. Adjust search criteria based on verified misses rather than increasing the scheduled item count. No live resource or result is required for the signed loopback integration test.
