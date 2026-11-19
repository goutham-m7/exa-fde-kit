# Does the client recover together or retry together?

    uv run python -m exa_fde_kit.loadtest --requests 30 --workers 8 --limit 10
    uv run python -m exa_fde_kit.loadtest --requests 30 --workers 8 --limit 10 --unpaced

**Loopback only, $0 spend.** The command starts an ephemeral HTTP server on 127.0.0.1, has no remote target option, ignores proxy settings, follows no redirects, and reads no key. Concurrent async workers call the existing synchronous client in threads. The server enforces a rolling one-second quota; its initial window is already full, simulating other traffic on the same credential. It sends a real HTTP 429 with a one-second Retry-After. Use --empty-start to remove that initial condition.

Both arms share a client, semaphore, bounded retry policy, jitter and cooldown. Paced admission also shares a capacity-one token bucket, targeting 98% of the configured quota rather than relying on millisecond-perfect request arrival. Sleeping workers must recheck admission; a prior 429 does not release a simultaneous burst at expiry. Already in-flight requests cannot be recalled. Long provider cooldowns fail fast while more than ten seconds remain. This is per-process coordination, not a distributed account-level limiter.

### Local measurement (19 Nov 2026)

One run of each command above, not a live Exa benchmark:

| Admission | Successful / 30 | Retries | HTTP 429 | Peak attempts in any 50 ms | Goodput (success/s) | Post-start goodput | p95 ms |
|---|---:|---:|---:|---:|---:|---:|---:|
| Paced | 30 | 1 | 1 | 1 | 7.33 | 9.43 | 3231 |
| Unpaced | 26 | 13 | 13 | 15 | 7.01 | 9.30 | 2045 |

The paced run paused for 1013 ms between the first rejection and the next arrival; the control saw another arrival within 1 ms. Pacing improved completion, not p95 in this run. Goodput includes initial cooldown and errors; post-start rate uses the interval from first to last successful arrival and omits initial wait. Peak is a rolling-window count, not fixed-bin averaging. p95 includes admission, retries and failed logical requests, measured once a worker starts a job. This is a closed-loop capacity probe, not an open-loop user-arrival model. OS scheduling and jitter vary; the tests assert bounded recovery, not exact timings or billing.

## How an FDE would use this with a customer

Reproduce the customer's worker count and account limit locally before changing production. Compare completions and burst size, not just average throughput. A low p95 with failed requests isn't a win. For a fleet, split the per-account quota across processes or introduce a coordinated limiter upstream. Never point a load generator at Exa to infer an account's quota.
