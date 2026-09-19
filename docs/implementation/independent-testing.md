# Parallel implementation and independent acceptance

Delivery plan revision 4, 2026-09-19. Three people own A, B and C and implement/test concurrently. The authoritative workspace is `/mnt/relex-kai` on `verda`. Service contract revision 6 details the shared interfaces; product behavior requirements remain unchanged.

This is a delivery specification. Runners and starter artifacts below are required deliverables, not commands verified to exist today.

Read [shared-interfaces.md](shared-interfaces.md), [http-api.md](http-api.md) and [contract-examples.json](contract-examples.json) as the exact baseline for G0. Shared cases CT-01 through CT-18 are specified there; C's browser scenarios are in the HTTP contract. Public examples may be checked against generated response schemas during development; this does not verify product behavior.

## Verification policy: real services

Verification follows [real-service-verification.md](real-service-verification.md). Run the actual implementation against real PostgreSQL, Qdrant, configured model/reviewer/embedding services, FastAPI and a browser wherever the required operation uses them. Synthetic input documents are encouraged; fake service responses are not acceptance evidence.

Contract tests, schema examples and fixture-service scenarios below are development aids. They may establish implementation readiness but cannot mark product behavior verified. Cross-slice live checks stay pending until real adapters are available. Independent code handoff remains allowed, explicitly labeled implementation-ready rather than live-verified; missing services are reported as blockers, never replaced by a mock pass.


## Common starter, then three concurrent tracks

G0 is bounded preparation before splitting implementation work. A supplies importable DTOs, complete port signatures, domain errors and adapter-driven conformance examples. Include staged artifacts/index-operation acknowledgements, not just request/response shapes. C supplies minimal packaging with independently installable test dependencies for each slice and inert package imports. Agree these dependencies up front; subsequent additions follow file ownership.

Check in and record a common starter commit and contract revision. Include synthetic examples for contexts, record pages, job capabilities, staged artifacts, reviewed candidates, releases, receipts and errors in the shared contract tests. Example/type validation is a development aid. G0 requires no completed evidence service, model workflow or production app.

G0 readiness means all three can import the same contracts and their owned entry points without the other concrete packages or credentials. Collecting a minimal test or checking JSON examples is optional development support, not product verification. Prose alone does not satisfy G0. This shared setup replaces the old A1-before-B/C sequence. After G0 all three implementation tracks run simultaneously; live acceptance runs as each operation's real dependencies become available.

## Independent development setups

| Slice | Real code | Development substitute boundary | Infrastructure | Development evidence establishes |
| --- | --- | --- | --- | --- |
| S-A | Evidence, auth, migrations, durable jobs, privacy, publication and release | B processing/rebuild/index callbacks; reviewed candidates as inputs; optional privacy detector | Isolated real PostgreSQL | Canonical persistence, authorization and lifecycle under controlled external outcomes |
| S-B | Memory, chunking, retrieval fusion/expansion, history, answer/review and index adapter | A canonical read, eligibility, lexical, normalization and staging ports | Deterministic: no external services. Live: own Qdrant and real generation/embedding endpoints | Workflow behavior and live semantic quality against controlled canonical evidence |
| S-C | Actual API routes, orchestration, frontend and browser interactions | A/B services injected into real app factory | Own test API server and real browser | HTTP and UI behavior without a completed backend domain implementation |

Substitutes implement a controllable contract scenario, not another person's full logic. Never replace the owned behavior being accepted. C's tests must execute the actual chat route and citation UI, rather than intercepting all HTTP calls with canned responses.

A's PostgreSQL tests may use a locally running PostgreSQL server through a direct driver connection, with one isolated database/schema per run; no database HTTP API is needed. Connection settings follow architecture.md. B/C standalone tests remain independent of that server.

Actual PostgreSQL execution is required for A's owned persistence behavior. B's model/index evidence uses real services. C's final browser verification uses the real A/B application services. Report fixture/deterministic checks only as development results; missing live dependencies mean unverified, never passed.

## Development runners and separate live runners

Each person supplies an independent development runner and setup instructions in the owned script directory. The development commands below may use declared substitutes and do not pass behavioral acceptance:

```sh
bash scripts/evidence/test-slice.sh --run-id a-dev
bash scripts/intelligence/test-slice.sh --mode deterministic --run-id b-dev
bash scripts/intelligence/test-slice.sh --mode live --run-id b-live
bash scripts/product/test-slice.sh --run-id c-dev
```

Each development runner must:

- Run with only G0 plus its own slice; other concrete implementations may be absent. Test collection must not load production bootstrap or global fixtures that require all services.
- Check prerequisites, give actionable setup instructions and fail on missing mandatory dependencies. Never silently switch a live lane to mocks.
- Allocate unique run-specific PostgreSQL databases/schemas, Qdrant collections, ports and output directories. Cleanup only resources created by that run. Never reset another person's database or corpus.
- Accept private configuration without logging credentials. B's deterministic mode needs no provider credentials.
- Return nonzero on failures or required unavailable checks. Report passed, failed and unverified cases separately and list substituted dependencies.
- Record source/contract revision, commands, safe IDs and observed assertions in the slice's evidence report.

Behavioral verification uses the separate verify-live.sh commands in real-service-verification.md. Those commands must use real dependencies and may therefore need another slice's real adapter. Run two instances with distinct run IDs to verify live resource isolation; if real dependencies are unavailable, mark that live check pending. Fixture isolation is development evidence only.

C separately coordinates one simultaneous A/B/C verify-live.sh run once all real runners/dependencies are available, recorded under G4. This uses real services, including the assembled application for C; fixture or development-runner concurrency does not pass it. It is not a prerequisite for independent implementation-ready handoff. A missing other slice leaves live verification pending without blocking that code handoff. Separate owned paths prevent file conflicts; resource names prevent service conflicts.

## Shared boundary conformance

A owns common adapter-driven cases under `backend/tests/contracts/`. Producers run them against real owned implementations; consumers run the relevant cases against their substitutes. Each slice supplies its adapter factories and does not import another slice's test helpers. Coordinate changes to shared cases rather than editing the same file concurrently.

Cover:

- Server-bound context, wrong-project and ownership rejection.
- Ordered record pages and complete chunk accounting; stale cursors/versions and unavailable receipts.
- Job capability stage/version/lease checks; retryable failures and unknown index-write outcomes.
- Canonical eligibility for candidate IDs/versions/hashes; inactive admin previews excluded from answer evidence.
- Reviewed candidate shapes, exact claim/receipt binding, release-changed outcomes and request idempotency.
- Safe error responses and no unchecked candidate content returned by routes.

Consumer substitutes help develop consumer handling; they are not real-service acceptance evidence. Contracts must not drift silently: use explicit revisions and coordinated producer/consumer updates. Conformance tests reduce drift; G1-G4 still verify the real composition.

## Separate slice acceptance from integration

For every A1-A4, B1-B4 and C1-C4 acceptance case, record its standalone result, substitutes and remaining integration assertion. Preserve all original requirements.

| Behavior | Independent development checks (not acceptance) | Required real-service check |
| --- | --- | --- |
| Upload and publication | A staging/publication with controlled callbacks; B valid artifacts from staged fixtures; C upload/job UI | G1 actual parsing, indexing, publication and member source access |
| Answer and citations | B-C1..9 with live providers; A candidate validation/release races; C route ordering and receipt interactions | G2 actual retrieval, independent review, release and authorized sources |
| Erasure and delayed writes | A barriers/retry with paused callbacks; B real index replacement/removal under fixture capabilities; C failed/retry states | G3 combined fencing and controlled-store cleanup, including late upserts |
| Access changes | A real session/repository controls; B denied/stale canonical reads; C CSRF and withheld-response handling | G4 no leaks through assembled browser/API/caches |
| Restart | A real job/database/checkpoint recovery; B checkpoint reload and index retry; C reload and fixture job discovery | G4 real service restart and durable product state |
| Concurrent resources | Isolated development resources | Two instances of each live runner and G4 simultaneous A/B/C live runners |

Independent code handoff may be implementation-ready with a list of pending live checks; another person's unfinished implementation cannot block that handoff. Only actually executed real-service behaviors receive live-verified status. Full product completion requires every required behavior and G1-G4 with real implementations/services and actual browser interaction.

## Ownership and handoff

A owns fixtures in `backend/tests/evidence/` and shared contract cases. B owns fixtures in `backend/tests/intelligence/`. C owns fixtures in `backend/tests/product/` and `frontend/tests/`, plus shared integration fixtures under `fixtures/implementation/`. No slice waits for C's shared fixtures to start.

Each person supplies setup/runner commands, tested revision, contract revision, resource names, deterministic/live evidence and remaining integration cases in `evidence-a.md`, `evidence-b.md` or `evidence-c.md`. Production composition uses real adapters; test substitutes must be explicitly selected in test-only composition and never become automatic production fallbacks.
