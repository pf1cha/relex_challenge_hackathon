# Parallel implementation and independent acceptance

Delivery plan revision 4, 2026-09-19. Three people own A, B and C and implement/test concurrently. The authoritative workspace is `/mnt/relex-kai` on `verda`. Service contract revision 3 and product behavior requirements remain unchanged.

This is a delivery specification. Runners and starter artifacts below are required deliverables, not commands verified to exist today.

## Common starter, then three concurrent tracks

G0 is bounded preparation before splitting implementation work. A supplies importable DTOs, complete port signatures, domain errors and adapter-driven conformance examples. Include staged artifacts/index-operation acknowledgements, not just request/response shapes. C supplies minimal packaging with independently installable test dependencies for each slice and inert package imports. Agree these dependencies up front; subsequent additions follow file ownership.

Check in and record a common starter commit and contract revision. Include synthetic examples for contexts, record pages, job capabilities, staged artifacts, reviewed candidates, releases, receipts and errors in the shared contract tests. Validate examples against actual types. G0 requires no completed evidence service, model workflow or production app.

Readiness means all three can import the same contracts and collect a minimal slice test without the other concrete packages or credentials. Prose alone does not satisfy G0. This shared setup replaces the old A1-before-B/C sequence. After G0 all three implementation and standalone acceptance tracks run simultaneously.

## Independent systems under test

| Slice | Real code | Substitute boundary | Infrastructure | Pass establishes |
| --- | --- | --- | --- | --- |
| S-A | Evidence, auth, migrations, durable jobs, privacy, publication and release | B processing/rebuild/index callbacks; reviewed candidates as inputs; optional privacy detector | Isolated real PostgreSQL | Canonical persistence, authorization and lifecycle under controlled external outcomes |
| S-B | Memory, chunking, retrieval fusion/expansion, history, answer/review and index adapter | A canonical read, eligibility, lexical, normalization and staging ports | Deterministic: no external services. Live: own Qdrant and real generation/embedding endpoints | Workflow behavior and live semantic quality against controlled canonical evidence |
| S-C | Actual API routes, orchestration, frontend and browser interactions | A/B services injected into real app factory | Own test API server and real browser | HTTP and UI behavior without a completed backend domain implementation |

Substitutes implement a controllable contract scenario, not another person's full logic. Never replace the owned behavior being accepted. C's tests must execute the actual chat route and citation UI, rather than intercepting all HTTP calls with canned responses.

A's PostgreSQL tests and C's browser tests are mandatory for their standalone passes. B reports deterministic and live lanes separately; missing live dependencies mean unverified, never passed.

## Required runners and isolation

Each person supplies a runner and setup instructions in the owned script directory. Required invocation shape from repository root:

```sh
bash scripts/evidence/test-slice.sh --run-id a-dev
bash scripts/intelligence/test-slice.sh --mode deterministic --run-id b-dev
bash scripts/intelligence/test-slice.sh --mode live --run-id b-live
bash scripts/product/test-slice.sh --run-id c-dev
```

Each runner must:

- Run with only G0 plus its own slice; other concrete implementations may be absent. Test collection must not load production bootstrap or global fixtures that require all services.
- Check prerequisites, give actionable setup instructions and fail on missing mandatory dependencies. Never silently switch a live lane to mocks.
- Allocate unique run-specific PostgreSQL databases/schemas, Qdrant collections, ports and output directories. Cleanup only resources created by that run. Never reset another person's database or corpus.
- Accept private configuration without logging credentials. B's deterministic mode needs no provider credentials.
- Return nonzero on failures or required unavailable checks. Report passed, failed and unverified cases separately and list substituted dependencies.
- Record source/contract revision, commands, safe IDs and observed assertions in the slice's evidence report.

Run S-A, S-B and S-C simultaneously once to establish isolation, and ensure repeated/concurrent runs of one slice also use unique resources. This parallel check requires no assembled application. Separate owned paths prevent file conflicts in the authoritative checkout; resource names prevent service conflicts.

## Shared boundary conformance

A owns common adapter-driven cases under `backend/tests/contracts/`. Producers run them against real owned implementations; consumers run the relevant cases against their substitutes. Each slice supplies its adapter factories and does not import another slice's test helpers. Coordinate changes to shared cases rather than editing the same file concurrently.

Cover:

- Server-bound context, wrong-project and ownership rejection.
- Ordered record pages and complete chunk accounting; stale cursors/versions and unavailable receipts.
- Job capability stage/version/lease checks; retryable failures and unknown index-write outcomes.
- Canonical eligibility for candidate IDs/versions/hashes; inactive admin previews excluded from answer evidence.
- Reviewed candidate shapes, exact claim/receipt binding, release-changed outcomes and request idempotency.
- Safe error responses and no unchecked candidate content returned by routes.

Consumer substitutes prove consumer handling, not real provider behavior. Contracts must not drift silently: use explicit revisions and coordinated producer/consumer updates. Conformance tests reduce drift; G1-G4 still verify the real composition.

## Separate slice acceptance from integration

For every A1-A4, B1-B4 and C1-C4 acceptance case, record its standalone result, substitutes and remaining integration assertion. Preserve all original requirements.

| Behavior | Standalone checks | Integration check |
| --- | --- | --- |
| Upload and publication | A staging/publication with controlled callbacks; B valid artifacts from staged fixtures; C upload/job UI | G1 actual parsing, indexing, publication and member source access |
| Answer and citations | B-C1..9 with live providers; A candidate validation/release races; C route ordering and receipt interactions | G2 actual retrieval, independent review, release and authorized sources |
| Erasure and delayed writes | A barriers/retry with paused callbacks; B real index replacement/removal under fixture capabilities; C failed/retry states | G3 combined fencing and controlled-store cleanup, including late upserts |
| Access changes | A real session/repository controls; B denied/stale canonical reads; C CSRF and withheld-response handling | G4 no leaks through assembled browser/API/caches |
| Restart | A real job/database recovery; B index retry; C reload and fixture job discovery | G4 real service restart and durable product state |

Independent handoff needs the slice's required checks and an explicit list of pending integration assertions. Another person's unfinished implementation cannot block that handoff. Full product completion still requires G1-G4 with real implementations/services and actual browser interaction.

## Ownership and handoff

A owns fixtures in `backend/tests/evidence/` and shared contract cases. B owns fixtures in `backend/tests/intelligence/`. C owns fixtures in `backend/tests/product/` and `frontend/tests/`, plus shared integration fixtures under `fixtures/implementation/`. No slice waits for C's shared fixtures to start.

Each person supplies setup/runner commands, tested revision, contract revision, resource names, deterministic/live evidence and remaining integration cases in `evidence-a.md`, `evidence-b.md` or `evidence-c.md`. Production composition uses real adapters; test substitutes must be explicitly selected in test-only composition and never become automatic production fallbacks.
