# Intelligence slice

Run from `/mnt/relex-kai` on `verda`. Production imports are inert. `Intelligence` receives contract ports, a provider, a Qdrant adapter, `RuntimeLimits`, and a private cursor signing key. It never imports the concrete evidence or API packages. C owns production composition.

Setup: install `backend[intelligence,evidence]` using C's project environment, or set `RELEX_PYTHON` to its Python executable. Provider configuration comes from the existing private `.env` when these explicit runners start: `RELEX_MODEL_BASE_URL`, `RELEX_MODEL_NAME`, `RELEX_MODEL_API_KEY`, `RELEX_EMBEDDING_BASE_URL`, `RELEX_EMBEDDING_MODEL`, `RELEX_EMBEDDING_API_KEY`; empty role keys fall back to `OPENAI_API_KEY`. No private config is loaded by package imports.

Start an owned persistent Qdrant process using `bash scripts/intelligence/start-qdrant.sh`. It downloads the pinned v1.14.1 Linux x86-64 binary into ignored runtime storage, binds loopback HTTP 16333 / gRPC 16334, and runs in the foreground. Set `RELEX_QDRANT_HTTP_PORT` / `RELEX_QDRANT_GRPC_PORT` for another owned instance. Never start a second process against the same storage. Existing process for this delivery is recorded in evidence-b.md.

Development only:

```sh
bash scripts/intelligence/test-slice.sh --mode deterministic --run-id b_dev
bash scripts/intelligence/test-slice.sh --mode live --run-id b_provider --case B-C1
```

Both use an explicitly substituted canonical repository/ledger. `--mode live` calls the actual model/embedding/Qdrant adapters but is still development evidence, never full product acceptance. Reports state the substituted boundaries.

Actual service verification:

```sh
RELEX_LIVE_DATABASE_URL=postgresql://relex_dev@127.0.0.1:15432/postgres \
  bash scripts/intelligence/verify-live.sh --run-id b_full
RELEX_LIVE_DATABASE_URL=postgresql://relex_dev@127.0.0.1:15432/postgres \
  bash scripts/intelligence/verify-live.sh --run-id b_negative --case B-C1 --negative
RELEX_LIVE_DATABASE_URL=postgresql://relex_dev@127.0.0.1:15432/postgres \
  bash scripts/intelligence/verify-live.sh --run-id b_stale --case B-C3 --stale
RELEX_LIVE_DATABASE_URL=postgresql://relex_dev@127.0.0.1:15432/postgres \
  bash scripts/intelligence/verify-live.sh --run-id b_long --retrieval
```

The displayed DSN is C's loopback synthetic PostgreSQL instance, not a production default. Missing DSN/adapters/dependencies produce BLOCKED/FAIL and exit 2. Each fresh run ID creates schema and collection `b_live_<run_id>`, retains them for inspection, and writes ignored reports under `scripts/intelligence/runs/<run_id>/`. Use fresh lowercase IDs (letters/digits/underscores, at most 36 characters); these runners intentionally do not destroy retained state. Private signing keys stay in chmod-600 ignored files. No credentials enter the JSON evidence.

The default real runner executes B-C1..B-C9 plus the mention-is-not-owner case, including actual upload processing, independent review, exact receipts, atomic A release, persisted reread using a new adapter, and idempotent chat replay/conflict. Optional probes use actual adapters with deliberately malformed candidates or an unavailable owned network route. Long retrieval checks filters, ordered pages, late qualification, exact lexical candidates and a deliberately stale Qdrant payload.

Exit 3 means the actual requested workflows executed, while the evidence still needs semantic review or other required acceptance rows remain unverified. It is deliberately not a blanket PASS. Source expected/prohibited outcomes, actual claims, candidate digests, safe tool traces and provider model/dimension observations are recorded for independent review. A owns process-crash/checkpoint and late-writer/erasure verification; C owns actual browser and combined-run verification. The evidence report maps remaining scenarios individually.

Resources are never automatically dropped. Stop only a process this run owns and remove only its explicitly named schema/collection when no other observer needs the retained evidence. Do not modify the corpus, private `.env`, other workers' schemas/collections, or host services.

Focused follow-ups reuse only a retained B-owned schema/collection via `probe-existing.py --run-id <id> --case <case>` with `--followup`, `--semantic-only`, `--bundle`, `--topics`, or `--artifact-negative`. The harness reloads the already authenticated server-side principal from that isolated schema; it is not authentication acceptance. Default follow-up mode tests lexical-only retrieval, wrong-project candidates, stale cursors and unchanged vectors. Negative artifact mode deliberately mutates actual real-model batch inputs before actual A staging while leaving PostgreSQL, Qdrant and the final model/reviewer/release code real. Every injected mutation is labeled in the output. These probes retain their own JSON files alongside the original run report.
