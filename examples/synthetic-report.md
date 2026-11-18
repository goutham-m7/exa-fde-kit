# Developer support retrieval eval: SYNTHETIC REPLAY — NOT LIVE

Synthetic rankings, publication dates and passages. Timing is local replay, not Exa latency. USD is hypothetical list-price arithmetic; actual API spend is $0. No production conclusion follows.

Run: 2026-11-18T18:19:07+00:00. Same cases per preset; one serial pass, seeded order within each case (42). No client cache.

| Preset | Cases | k | Domain recall@k | Supported cites | Supported answers | Blank | Errors | p50 ms | p95 ms | Known/est. USD | Unknown-cost attempts |
|---|---:|---:|---:|---:|---:|---:|---:|---:|---:|---:|---:|
| baseline | 24 | 3 | 100.0% | 19/25 | 19/24 | 0 | 0 | 0.17 | 0.19 | 0.2400 | 0 |
| lite | 24 | 3 | 95.8% | 15/25 | 15/24 | 0 | 0 | 0.17 | 0.22 | 0.1680 | 0 |
| wide | 24 | 5 | 100.0% | 23/25 | 23/24 | 0 | 0 | 0.19 | 0.23 | 0.2880 | 0 |
| summary | 24 | 3 | 100.0% | 14/28 | 14/24 | 0 | 0 | 0.17 | 0.22 | 0.2400 | 0 |
| recent | 24 | 3 | 89.6% | 16/24 | 16/24 | 0 | 0 | 0.17 | 0.20 | 0.2380 | 0 |

Support is a proxy, not an entailment judge: an emitted passage must come from an expected domain and contain an independently labeled fact alias. Blank/error answers remain in the answer denominator. A blank answer has no citations and does not improve citation precision. Recall is the mean fraction of expected domains in the first k search results. Latencies include both stages, retries and failures (nearest rank).

## Compared settings

- **baseline:** auto, k=3, highlights, published since any time.
- **lite:** lite, k=3, highlights, published since any time.
- **wide:** auto, k=5, highlights, published since any time.
- **summary:** auto, k=3, summary, published since any time.
- **recent:** auto, k=3, highlights, published since 2024-01-01T00:00:00Z.

## Case audit

| Case | Preset | Expected domains | Recall | Supported / cited | Result |
|---|---|---|---:|---:|---|
| py-tasks | summary | docs.python.org | 100% | 1/2 | answer |
| py-tasks | lite | docs.python.org | 100% | 1/1 | answer |
| py-tasks | wide | docs.python.org | 100% | 1/1 | answer |
| py-tasks | recent | docs.python.org | 100% | 0/1 | answer |
| py-tasks | baseline | docs.python.org | 100% | 1/1 | answer |
| py-timeout | summary | docs.python.org | 100% | 1/2 | answer |
| py-timeout | wide | docs.python.org | 100% | 1/1 | answer |
| py-timeout | baseline | docs.python.org | 100% | 1/1 | answer |
| py-timeout | recent | docs.python.org | 100% | 1/1 | answer |
| py-timeout | lite | docs.python.org | 100% | 0/1 | answer |
| py-venv | summary | docs.python.org | 100% | 0/1 | answer |
| py-venv | lite | docs.python.org | 100% | 1/1 | answer |
| py-venv | wide | docs.python.org | 100% | 1/1 | answer |
| py-venv | baseline | docs.python.org | 100% | 1/1 | answer |
| py-venv | recent | docs.python.org | 100% | 1/1 | answer |
| pip-hashes | lite | pip.pypa.io | 100% | 1/1 | answer |
| pip-hashes | wide | pip.pypa.io | 100% | 1/1 | answer |
| pip-hashes | summary | pip.pypa.io | 100% | 0/1 | answer |
| pip-hashes | recent | pip.pypa.io | 0% | 0/1 | answer |
| pip-hashes | baseline | pip.pypa.io | 100% | 1/1 | answer |
| packaging-entry | recent | packaging.python.org | 100% | 1/1 | answer |
| packaging-entry | summary | packaging.python.org | 100% | 1/1 | answer |
| packaging-entry | wide | packaging.python.org | 100% | 1/1 | answer |
| packaging-entry | baseline | packaging.python.org | 100% | 1/1 | answer |
| packaging-entry | lite | packaging.python.org | 100% | 1/1 | answer |
| k8-ready | wide | kubernetes.io | 100% | 1/1 | answer |
| k8-ready | lite | kubernetes.io | 100% | 0/1 | answer |
| k8-ready | baseline | kubernetes.io | 100% | 0/1 | answer |
| k8-ready | summary | kubernetes.io | 100% | 0/1 | answer |
| k8-ready | recent | kubernetes.io | 100% | 1/1 | answer |
| k8-drain | lite | kubernetes.io | 100% | 1/1 | answer |
| k8-drain | summary | kubernetes.io | 100% | 1/1 | answer |
| k8-drain | baseline | kubernetes.io | 100% | 1/1 | answer |
| k8-drain | wide | kubernetes.io | 100% | 1/1 | answer |
| k8-drain | recent | kubernetes.io | 100% | 0/1 | answer |
| k8-rollout | recent | kubernetes.io | 100% | 1/1 | answer |
| k8-rollout | baseline | kubernetes.io | 100% | 1/1 | answer |
| k8-rollout | lite | kubernetes.io | 100% | 0/1 | answer |
| k8-rollout | wide | kubernetes.io | 100% | 1/1 | answer |
| k8-rollout | summary | kubernetes.io | 100% | 0/1 | answer |
| k8-resources | recent | kubernetes.io | 100% | 1/1 | answer |
| k8-resources | summary | kubernetes.io | 100% | 1/1 | answer |
| k8-resources | baseline | kubernetes.io | 100% | 1/1 | answer |
| k8-resources | wide | kubernetes.io | 100% | 1/1 | answer |
| k8-resources | lite | kubernetes.io | 100% | 1/1 | answer |
| docker-cache | recent | docs.docker.com | 100% | 0/1 | answer |
| docker-cache | wide | docs.docker.com | 100% | 1/2 | answer |
| docker-cache | lite | docs.docker.com | 100% | 1/2 | answer |
| docker-cache | baseline | docs.docker.com | 100% | 1/2 | answer |
| docker-cache | summary | docs.docker.com | 100% | 0/1 | answer |
| docker-context | summary | docs.docker.com | 100% | 1/1 | answer |
| docker-context | lite | docs.docker.com | 100% | 1/1 | answer |
| docker-context | baseline | docs.docker.com | 100% | 1/1 | answer |
| docker-context | wide | docs.docker.com | 100% | 1/1 | answer |
| docker-context | recent | docs.docker.com | 100% | 1/1 | answer |
| docker-signal | wide | docs.docker.com | 100% | 1/1 | answer |
| docker-signal | summary | docs.docker.com | 100% | 0/1 | answer |
| docker-signal | lite | docs.docker.com | 100% | 0/1 | answer |
| docker-signal | baseline | docs.docker.com | 100% | 0/1 | answer |
| docker-signal | recent | docs.docker.com | 100% | 1/1 | answer |
| pg-index | baseline | postgresql.org | 100% | 1/1 | answer |
| pg-index | lite | postgresql.org | 100% | 1/1 | answer |
| pg-index | summary | postgresql.org | 100% | 1/1 | answer |
| pg-index | wide | postgresql.org | 100% | 1/1 | answer |
| pg-index | recent | postgresql.org | 100% | 0/1 | answer |
| pg-timeout | summary | postgresql.org | 100% | 1/1 | answer |
| pg-timeout | baseline | postgresql.org | 100% | 1/1 | answer |
| pg-timeout | wide | postgresql.org | 100% | 1/1 | answer |
| pg-timeout | lite | postgresql.org | 100% | 0/1 | answer |
| pg-timeout | recent | postgresql.org | 100% | 1/1 | answer |
| pg-plan | wide | postgresql.org | 100% | 1/1 | answer |
| pg-plan | recent | postgresql.org | 100% | 1/1 | answer |
| pg-plan | summary | postgresql.org | 100% | 1/1 | answer |
| pg-plan | lite | postgresql.org | 100% | 1/1 | answer |
| pg-plan | baseline | postgresql.org | 100% | 1/1 | answer |
| sqlite-wal | summary | sqlite.org | 100% | 1/1 | answer |
| sqlite-wal | wide | sqlite.org | 100% | 1/1 | answer |
| sqlite-wal | recent | sqlite.org | 0% | 0/1 | answer |
| sqlite-wal | baseline | sqlite.org | 100% | 1/1 | answer |
| sqlite-wal | lite | sqlite.org | 100% | 1/1 | answer |
| sqlite-fk | recent | sqlite.org | 100% | 1/1 | answer |
| sqlite-fk | lite | sqlite.org | 100% | 1/1 | answer |
| sqlite-fk | baseline | sqlite.org | 100% | 1/1 | answer |
| sqlite-fk | wide | sqlite.org | 100% | 1/1 | answer |
| sqlite-fk | summary | sqlite.org | 100% | 0/1 | answer |
| git-undo | baseline | git-scm.com | 100% | 0/1 | answer |
| git-undo | summary | git-scm.com | 100% | 0/1 | answer |
| git-undo | recent | git-scm.com | 100% | 1/1 | answer |
| git-undo | lite | git-scm.com | 100% | 0/1 | answer |
| git-undo | wide | git-scm.com | 100% | 1/1 | answer |
| git-find | summary | git-scm.com | 100% | 0/2 | answer |
| git-find | recent | git-scm.com | 100% | 0/1 | answer |
| git-find | wide | git-scm.com | 100% | 0/1 | answer |
| git-find | lite | git-scm.com | 100% | 0/1 | answer |
| git-find | baseline | git-scm.com | 100% | 0/1 | answer |
| rust-lock | baseline | doc.rust-lang.org | 100% | 1/1 | answer |
| rust-lock | wide | doc.rust-lang.org | 100% | 1/1 | answer |
| rust-lock | recent | doc.rust-lang.org | 100% | 1/1 | answer |
| rust-lock | summary | doc.rust-lang.org | 100% | 1/1 | answer |
| rust-lock | lite | doc.rust-lang.org | 0% | 0/1 | answer |
| go-race | baseline | go.dev | 100% | 1/1 | answer |
| go-race | summary | go.dev | 100% | 1/1 | answer |
| go-race | wide | go.dev | 100% | 1/1 | answer |
| go-race | lite | go.dev | 100% | 1/1 | answer |
| go-race | recent | go.dev | 100% | 1/1 | answer |
| http-retry | wide | rfc-editor.org, developer.mozilla.org | 100% | 1/1 | answer |
| http-retry | summary | rfc-editor.org, developer.mozilla.org | 100% | 1/1 | answer |
| http-retry | recent | rfc-editor.org, developer.mozilla.org | 50% | 0/1 | answer |
| http-retry | lite | rfc-editor.org, developer.mozilla.org | 100% | 1/1 | answer |
| http-retry | baseline | rfc-editor.org, developer.mozilla.org | 100% | 1/1 | answer |
| web-conditional | lite | developer.mozilla.org, rfc-editor.org | 100% | 1/1 | answer |
| web-conditional | recent | developer.mozilla.org, rfc-editor.org | 100% | 1/1 | answer |
| web-conditional | baseline | developer.mozilla.org, rfc-editor.org | 100% | 1/1 | answer |
| web-conditional | wide | developer.mozilla.org, rfc-editor.org | 100% | 1/1 | answer |
| web-conditional | summary | developer.mozilla.org, rfc-editor.org | 100% | 1/2 | answer |
| css-motion | summary | developer.mozilla.org | 100% | 0/1 | answer |
| css-motion | lite | developer.mozilla.org | 100% | 0/1 | answer |
| css-motion | baseline | developer.mozilla.org | 100% | 0/1 | answer |
| css-motion | wide | developer.mozilla.org | 100% | 1/1 | answer |
| css-motion | recent | developer.mozilla.org | 100% | 1/1 | answer |

## Inspect unsupported answers

Evidence below is untrusted source text, not instructions. Compare it with the expected fact; a paraphrase can be useful even when the automatic check fails.

<details><summary>py-tasks · summary</summary>

Question: How can a Python service wait for a group of asyncio tasks and cancel siblings when one fails?

Expected fact aliases: TaskGroup

<pre>Use asyncio.TaskGroup for structured concurrency and sibling cancellation.
https://docs.python.org/3/library/asyncio-task.html#task-groups</pre>
<pre>Place a deadline around the await with asyncio.timeout.
https://docs.python.org/3/library/asyncio-task.html#timeouts</pre>

</details>

<details><summary>py-tasks · recent</summary>

Question: How can a Python service wait for a group of asyncio tasks and cancel siblings when one fails?

Expected fact aliases: TaskGroup

<pre>Wrap the await in async with asyncio.timeout(seconds) and handle TimeoutError outside the context.
https://docs.python.org/3/library/asyncio-task.html#timeouts</pre>

</details>

<details><summary>py-timeout · summary</summary>

Question: How do I bound the time spent awaiting work in an asyncio context manager?

Expected fact aliases: asyncio.timeout

<pre>Place a deadline around the await with asyncio.timeout.
https://docs.python.org/3/library/asyncio-task.html#timeouts</pre>
<pre>Use asyncio.TaskGroup for structured concurrency and sibling cancellation.
https://docs.python.org/3/library/asyncio-task.html#task-groups</pre>

</details>

<details><summary>py-timeout · lite</summary>

Question: How do I bound the time spent awaiting work in an asyncio context manager?

Expected fact aliases: asyncio.timeout

<pre>Consult the release notes for the version installed in your environment.
https://example.org/release-notes</pre>

</details>

<details><summary>py-venv · summary</summary>

Question: How should a teammate recreate a Python virtual environment after moving a project?

Expected fact aliases: recreate, re-create, recreating

<pre>Virtual environments are disposable and are not designed to be moved.
https://docs.python.org/3/library/venv.html</pre>

</details>

<details><summary>pip-hashes · summary</summary>

Question: Which pip install option requires hashes for every dependency in a locked requirements file?

Expected fact aliases: --require-hashes

<pre>Hash-checking mode verifies each distribution against the supplied digests.
https://pip.pypa.io/en/stable/topics/secure-installs/</pre>

</details>

<details><summary>pip-hashes · recent</summary>

Question: Which pip install option requires hashes for every dependency in a locked requirements file?

Expected fact aliases: --require-hashes

<pre>Wrap the await in async with asyncio.timeout(seconds) and handle TimeoutError outside the context.
https://docs.python.org/3/library/asyncio-task.html#timeouts</pre>

</details>

<details><summary>k8-ready · lite</summary>

Question: Which Kubernetes probe keeps a starting pod out of Service endpoints without restarting it?

Expected fact aliases: readiness

<pre>Consult the release notes for the version installed in your environment.
https://example.org/release-notes</pre>

</details>

<details><summary>k8-ready · baseline</summary>

Question: Which Kubernetes probe keeps a starting pod out of Service endpoints without restarting it?

Expected fact aliases: readiness

<pre>Consult the release notes for the version installed in your environment.
https://example.org/release-notes</pre>

</details>

<details><summary>k8-ready · summary</summary>

Question: Which Kubernetes probe keeps a starting pod out of Service endpoints without restarting it?

Expected fact aliases: readiness

<pre>Release documentation can clarify version-specific behavior.
https://example.org/release-notes</pre>

</details>

<details><summary>k8-drain · recent</summary>

Question: What limits voluntary disruptions when we drain a node serving a replicated application?

Expected fact aliases: PodDisruptionBudget, disruption budget

<pre>A failing readiness probe marks the pod unready for Service traffic; unlike a liveness failure it does not restart the container.
https://kubernetes.io/docs/concepts/configuration/liveness-readiness-startup-probes/</pre>

</details>

<details><summary>k8-rollout · lite</summary>

Question: What command reverts a failed Kubernetes Deployment rollout to its previous revision?

Expected fact aliases: rollout undo

<pre>Consult the release notes for the version installed in your environment.
https://example.org/release-notes</pre>

</details>

<details><summary>k8-rollout · summary</summary>

Question: What command reverts a failed Kubernetes Deployment rollout to its previous revision?

Expected fact aliases: rollout undo

<pre>Deployments retain a revision history that supports rollback.
https://kubernetes.io/docs/concepts/workloads/controllers/deployment/</pre>

</details>

<details><summary>docker-cache · recent</summary>

Question: How can I keep downloaded packages across Dockerfile build steps without putting them in the image?

Expected fact aliases: type=cache

<pre>A .dockerignore file excludes matching files before the build context is sent.
https://docs.docker.com/build/concepts/context/</pre>

</details>

<details><summary>docker-cache · wide</summary>

Question: How can I keep downloaded packages across Dockerfile build steps without putting them in the image?

Expected fact aliases: type=cache

<pre>Use RUN --mount=type=cache,target=/path/to/cache to reuse a package cache across builds.
https://docs.docker.com/build/cache/optimize/</pre>
<pre>A .dockerignore file excludes matching files before the build context is sent.
https://docs.docker.com/build/concepts/context/</pre>

</details>

<details><summary>docker-cache · lite</summary>

Question: How can I keep downloaded packages across Dockerfile build steps without putting them in the image?

Expected fact aliases: type=cache

<pre>Use RUN --mount=type=cache,target=/path/to/cache to reuse a package cache across builds.
https://docs.docker.com/build/cache/optimize/</pre>
<pre>A .dockerignore file excludes matching files before the build context is sent.
https://docs.docker.com/build/concepts/context/</pre>

</details>

<details><summary>docker-cache · baseline</summary>

Question: How can I keep downloaded packages across Dockerfile build steps without putting them in the image?

Expected fact aliases: type=cache

<pre>Use RUN --mount=type=cache,target=/path/to/cache to reuse a package cache across builds.
https://docs.docker.com/build/cache/optimize/</pre>
<pre>A .dockerignore file excludes matching files before the build context is sent.
https://docs.docker.com/build/concepts/context/</pre>

</details>

<details><summary>docker-cache · summary</summary>

Question: How can I keep downloaded packages across Dockerfile build steps without putting them in the image?

Expected fact aliases: type=cache

<pre>Use .dockerignore patterns to keep local artifacts out.
https://docs.docker.com/build/concepts/context/</pre>

</details>

<details><summary>docker-signal · summary</summary>

Question: Which Dockerfile ENTRYPOINT form lets the executable receive the stop signal directly?

Expected fact aliases: exec form

<pre>Release documentation can clarify version-specific behavior.
https://example.org/release-notes</pre>

</details>

<details><summary>docker-signal · lite</summary>

Question: Which Dockerfile ENTRYPOINT form lets the executable receive the stop signal directly?

Expected fact aliases: exec form

<pre>Consult the release notes for the version installed in your environment.
https://example.org/release-notes</pre>

</details>

<details><summary>docker-signal · baseline</summary>

Question: Which Dockerfile ENTRYPOINT form lets the executable receive the stop signal directly?

Expected fact aliases: exec form

<pre>Consult the release notes for the version installed in your environment.
https://example.org/release-notes</pre>

</details>

<details><summary>pg-index · recent</summary>

Question: How can we build a PostgreSQL index without blocking concurrent writes to the table?

Expected fact aliases: concurrently

<pre>lock_timeout cancels a statement that waits too long to acquire a lock.
https://www.postgresql.org/docs/current/runtime-config-client.html</pre>

</details>

<details><summary>pg-timeout · lite</summary>

Question: Which PostgreSQL setting limits only the time spent waiting to acquire a lock?

Expected fact aliases: lock_timeout

<pre>Consult the release notes for the version installed in your environment.
https://example.org/release-notes</pre>

</details>

<details><summary>sqlite-wal · recent</summary>

Question: Which SQLite journal mode lets readers continue while a writer records changes?

Expected fact aliases: WAL, write-ahead logging

<pre>lock_timeout cancels a statement that waits too long to acquire a lock.
https://www.postgresql.org/docs/current/runtime-config-client.html</pre>

</details>

<details><summary>sqlite-fk · summary</summary>

Question: Which SQLite pragma enables enforcement of foreign key constraints on a connection?

Expected fact aliases: foreign_keys

<pre>Foreign key checking is a connection-level setting.
https://sqlite.org/foreignkeys.html</pre>

</details>

<details><summary>git-undo · baseline</summary>

Question: Which Git command records a new commit that reverses an already shared commit?

Expected fact aliases: git revert

<pre>git bisect asks you to classify successive revisions as good or bad and narrows down the range.
https://git-scm.com/docs/git-bisect</pre>

</details>

<details><summary>git-undo · summary</summary>

Question: Which Git command records a new commit that reverses an already shared commit?

Expected fact aliases: git revert

<pre>Release documentation can clarify version-specific behavior.
https://example.org/release-notes</pre>

</details>

<details><summary>git-undo · lite</summary>

Question: Which Git command records a new commit that reverses an already shared commit?

Expected fact aliases: git revert

<pre>git bisect asks you to classify successive revisions as good or bad and narrows down the range.
https://git-scm.com/docs/git-bisect</pre>

</details>

<details><summary>git-find · summary</summary>

Question: How can I locate the first bad Git commit by repeatedly testing halfway through history?

Expected fact aliases: git bisect

<pre>Bisect the history between a known good and a known bad revision.
https://git-scm.com/docs/git-bisect</pre>
<pre>Use git revert on a published commit.
https://git-scm.com/docs/git-revert</pre>

</details>

<details><summary>git-find · recent</summary>

Question: How can I locate the first bad Git commit by repeatedly testing halfway through history?

Expected fact aliases: git bisect

<pre>git revert makes another commit that undoes the selected change without rewriting the shared history.
https://git-scm.com/docs/git-revert</pre>

</details>

<details><summary>git-find · wide</summary>

Question: How can I locate the first bad Git commit by repeatedly testing halfway through history?

Expected fact aliases: git bisect

<pre>git revert makes another commit that undoes the selected change without rewriting the shared history.
https://git-scm.com/docs/git-revert</pre>

</details>

<details><summary>git-find · lite</summary>

Question: How can I locate the first bad Git commit by repeatedly testing halfway through history?

Expected fact aliases: git bisect

<pre>git revert makes another commit that undoes the selected change without rewriting the shared history.
https://git-scm.com/docs/git-revert</pre>

</details>

<details><summary>git-find · baseline</summary>

Question: How can I locate the first bad Git commit by repeatedly testing halfway through history?

Expected fact aliases: git bisect

<pre>git revert makes another commit that undoes the selected change without rewriting the shared history.
https://git-scm.com/docs/git-revert</pre>

</details>

<details><summary>rust-lock · lite</summary>

Question: How do I make Cargo fail if building would require changing the lockfile?

Expected fact aliases: --locked

<pre>Consult the release notes for the version installed in your environment.
https://example.org/release-notes</pre>

</details>

<details><summary>http-retry · recent</summary>

Question: Where do HTTP semantics and browser docs define how long to wait after a 503?

Expected fact aliases: Retry-After

<pre>Send the saved ETag in If-None-Match to validate a stored response.
https://developer.mozilla.org/en-US/docs/Web/HTTP/Reference/Headers/If-None-Match</pre>

</details>

<details><summary>web-conditional · summary</summary>

Question: Which request header sends an ETag back to a server to revalidate a cached response?

Expected fact aliases: If-None-Match

<pre>The 503 response can include Retry-After to suggest a delay.
https://www.rfc-editor.org/rfc/rfc9110.html#name-retry-after</pre>
<pre>A client can revalidate using If-None-Match.
https://www.rfc-editor.org/rfc/rfc9110.html#name-if-none-match</pre>

</details>

<details><summary>css-motion · summary</summary>

Question: How can a web component respect an operating system preference for reduced animations?

Expected fact aliases: prefers-reduced-motion

<pre>Release documentation can clarify version-specific behavior.
https://example.org/release-notes</pre>

</details>

<details><summary>css-motion · lite</summary>

Question: How can a web component respect an operating system preference for reduced animations?

Expected fact aliases: prefers-reduced-motion

<pre>Consult the release notes for the version installed in your environment.
https://example.org/release-notes</pre>

</details>

<details><summary>css-motion · baseline</summary>

Question: How can a web component respect an operating system preference for reduced animations?

Expected fact aliases: prefers-reduced-motion

<pre>Consult the release notes for the version installed in your environment.
https://example.org/release-notes</pre>

</details>

