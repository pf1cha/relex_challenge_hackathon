# Codebase architecture

Revision 3, 2026-09-19. Applies only to `/scratch/project_2020551/relex-0919`. This is the implementation structure for the source behavior/agent docs, not a replacement for their requirements. Folder READMEs are scaffolding; application code is still to be implemented.

## Structure

Use a modular backend with one HTTP process and one durable job process, plus a separate frontend application. Both backend processes use the same Python package and database contracts. No microservice framework, message broker or graph database is needed for the initial delivery.

```text
relex-0919/
├── backend/
│   ├── README.md
│   ├── pyproject.toml                 # C: dependencies, packaging, checks
│   ├── app/
│   │   ├── __init__.py                # C
│   │   ├── main.py                    # C: ASGI application factory
│   │   ├── worker.py                  # C: durable job process entry point
│   │   ├── bootstrap.py               # C: composition/dependency injection
│   │   ├── config.py                  # C: validated private server config
│   │   ├── contracts/                # A: shared types and service protocols
│   │   │   ├── models.py              # evidence, jobs, answers, conversations
│   │   │   ├── ports.py               # injected repository/provider interfaces
│   │   │   └── errors.py              # domain errors; no HTTP dependencies
│   │   ├── evidence/                 # A: canonical data and lifecycle
│   │   │   ├── auth.py                # sessions and project memberships
│   │   │   ├── documents.py           # ingestion and document lifecycle
│   │   │   ├── parsing.py             # source boundaries and duplicate lineage
│   │   │   ├── privacy.py             # identities, occurrences, normalization
│   │   │   ├── sources.py             # source/receipt resolution
│   │   │   ├── eligibility.py         # authorization, versions, release gate
│   │   │   ├── conversations.py       # owned chats and answer persistence
│   │   │   ├── erasure.py             # inventory, quarantine, resumable cleanup
│   │   │   ├── jobs.py                # leases, stages, retry, publication
│   │   │   └── postgres.py            # canonical persistence adapter
│   │   ├── intelligence/             # B: model/retrieval workflows
│   │   │   ├── maintenance.py         # L1/L2, topics and project overview
│   │   │   ├── chunking.py            # ordered chunks from canonical spans
│   │   │   ├── retrieval.py           # hybrid ranking and record expansion
│   │   │   ├── history.py             # scoped evidence-linked change notes
│   │   │   ├── answering.py           # bounded answer workflow
│   │   │   ├── grounding.py           # independent review and one repair
│   │   │   ├── tools.py               # context-bound read-only tools
│   │   │   ├── providers.py           # generation/embedding transport adapter
│   │   │   ├── qdrant.py              # rebuildable vector index adapter
│   │   │   ├── reconciliation.py      # stale/orphan detection and repair
│   │   │   └── prompts/               # separate maintenance/answer/review prompts
│   │   └── api/                      # C: thin HTTP adapters
│   │       ├── dependencies.py        # session -> server-created context
│   │       ├── errors.py              # domain errors -> safe HTTP responses
│   │       └── routes/                # auth, projects, documents, sources,
│   │                                 # chat, search, people, members, jobs
│   ├── migrations/                   # A: SQL schema and migration runner
│   └── tests/{evidence,intelligence,product}/
├── frontend/
│   ├── README.md
│   ├── package.json                   # C: build, typecheck, UI test commands
│   ├── src/
│   │   ├── app/                      # routing, project/session state
│   │   ├── api/                      # generated types plus HTTP client
│   │   ├── features/
│   │   │   ├── auth/
│   │   │   ├── documents/
│   │   │   ├── search/
│   │   │   ├── chat/
│   │   │   ├── sources/
│   │   │   ├── administration/
│   │   │   └── visualization/        # selector/status; actual view deferred
│   │   └── components/               # reused citation, job and error UI
│   ├── public/                       # non-sensitive static assets only
│   └── tests/                        # interaction tests and browser workflows
├── scripts/{evidence,intelligence,product}/
├── fixtures/implementation/          # C: shared synthetic acceptance inputs
├── docs/implementation/              # specs, architecture, review, evidence
├── corpus/                          # existing user input; preserve
└── .env                             # existing private config; never overwrite
```

File names inside modules are the target decomposition, not a requirement to create empty files. Start each module when its first slice needs it. Keep Python under the `app` package; avoid a top-level `platform` package that can shadow Python's standard library. Frontend framework/bundler is C's implementation choice; backend authorization and evidence semantics must not depend on that choice.

## Dependency direction and ownership

```text
frontend --HTTP--> api --calls--> injected evidence/intelligence services
                               |
bootstrap creates concrete adapters and registers job handlers
evidence ------> contracts <------ intelligence
   |                                  |
PostgreSQL                     model provider + Qdrant
```

Contracts depend on neither concrete package. Intelligence receives canonical-read, staging, lexical-search and artifact-write ports; it does not open ad hoc SQL connections or import `evidence.postgres`. Evidence invokes registered processing/index-removal callbacks through ports, never imports intelligence. API routes convert transport inputs, call services and map errors; business rules remain in A/B. Only bootstrap imports both concrete packages to wire them together.

B owns provider transport shared by model roles. If A needs model-assisted privacy detection, C injects a provider implementing the contracts protocol into A; A does not import B. Raw-sensitive privacy processing is a separate restricted operation from tokenized maintenance/answer calls. Its use requires appropriate endpoint/data authorization; synthetic probes are the default. Do not claim that every possible privacy-detector call is already tokenized.

A owns canonical ordered source spans; B owns chunking. B stages chunk descriptors (IDs, ordered span references, offsets for overlap, input hashes) through A's repository port. A's RecordPage resolves these descriptors back to canonical text and does not implement a second chunker. A provides scoped lexical candidates from canonical memory/chunk inputs; B fuses them with Qdrant candidates. This keeps SQL ownership and retrieval policy separate.

## Runtime and publication

- `backend/app/main.py` creates the HTTP application; it does not launch hidden background threads or run schema migrations on every request.
- `backend/app/worker.py` starts the durable jobs loop. Both entry points use the same bootstrap and configured adapters. C documents explicit migration, bootstrap, HTTP and worker commands.
- A records a job and sanitized staged version. A job-scoped capability lets B read only that version. B stages validated artifacts and Qdrant entries; A publishes after verifying version/dependency readiness. Public source, search and tools reject staged entries.
- New records invalidate affected topic/project summaries and cached current-state answers. Invalidation occurs before the rebuild, with explicit pending state; no false complete overview.
- Erasure/deactivation revokes eligibility first, then jobs clean/rebuild derived stores. Failed jobs retain quarantine. Durable lease expiry and idempotency keys allow restart without duplicate publication.
- Final answer validation and persistence share a short SQL transaction serialized against relevant project mutations. The commit defines release order; HTTP delivery is not held under a database lock. Later reads always revalidate.

### Erasure, job fencing and index generations

Leases alone do not prevent an expired worker from finishing an old network call. A assigns monotonic lifecycle revisions and lease tokens; every staged SQL write, publication and job acknowledgement uses compare-and-set against them. B uses immutable version-specific Qdrant point IDs, so an old version cannot overwrite the current version. Track intended and completed index operations durably, including timeouts with unknown remote outcome; reconcile them before successful cleanup. A checks index entry version/hash against SQL, not the project's newest global revision, preserving unrelated vectors.

For v1, person/document erasure sets a project write barrier before inventory. Reject new uploads, identity mutations and chat persistence while it is active, and supersede ordinary maintenance jobs; allow cleanup/retry jobs and reads of unaffected data. Wait for all pre-barrier provider/index operations to finish or be proven stopped, then delete their obsolete outputs and verify the final inventory. Do not reclaim a writer with an unknown outstanding remote write and immediately mark erasure complete. A timeout with uncertain outcome keeps the job pending/failed until reconciliation establishes cleanup. Content-producing jobs accepted before the barrier are included in the inventory; their old tokens cannot republish. Release the barrier only after cleanup verification. This deliberately trades temporary write availability for a tractable deletion guarantee.

Test a paused index upsert that completes after erasure starts, a worker losing its lease, a queued upload and a chat finishing during erasure. None may restore deleted content or create a premature completed state. Do not preserve deleted names in a permanent denylist; newly submitted information after completed erasure is a new ingestion event, outside the completed job's inventory.

### Aggregate publication and displayed claims

Publish sanitized records plus their required per-record memories/chunks first; mark affected topic/overview artifacts pending in the same transaction. Build aggregates against that published snapshot and compare dependencies at aggregate publication. Retried aggregate jobs never block access to unrelated valid source records. A model-generated topic/overview is internal routing material until its displayed factual claims have passed B's grounding review against canonical spans. C's overview endpoint returns reviewed claims and receipts, or pending/failure; it never renders unchecked level-2 prose as a factual answer. Search uses canonical excerpts; model descriptions are discovery metadata, not an uncited substitute for answer claims.

### Receipt and conversation lifecycle

For revision 3 choose the source docs' permitted unavailable behavior for version changes: an answer receipt whose record version or answer generation changed returns 410 and requests regeneration. It is not silently remapped to a new quote supporting potentially different wording. Direct source navigation can display current eligible sanitized content, but old-version deep links return unavailable. Citation popovers re-fetch the receipt before displaying a quote; source pages independently authorize. Corpus/privacy/access changes and logout invalidate follow-up context; load history server-side, remove invalid assistant evidence and normalize retained messages before provider calls.

## Data model changes from the DBML sketch

Keep organizations/projects/users/memberships as recognizable concepts. Use project-scoped person identities separately from login users. Add documents -> records -> versioned source spans, chunk descriptors, artifacts/dependencies, reviewed change notes, jobs/outbox, privacy occurrence inventory and corpus/privacy/access revisions. Keep conversation/message/answer ownership and evidence dependencies explicit.

Do not require fixed structured decision rows for level 2 prose. If structured claims are used for final answers, that does not require all persisted summaries to use the same schema. Move vector ownership to Qdrant and detect dimension from the configured embedding provider. Replace person-name fields in derived data with opaque IDs/source references. Replace `purged_name` audit fields with operation IDs, counts and outcomes. Keep source timezone/date precision and effective/learned/source times distinct.

## Frontend/backend boundary

Frontend uses only authenticated HTTP APIs, never direct SQL/Qdrant/model access. Backend exports OpenAPI from its actual routes and contract DTOs; C generates frontend types/client with a documented command and checks regeneration drift. Do not hand-maintain a second evidence schema in TypeScript.

Development uses a same-origin proxy; deployment may serve compiled `frontend/dist/` from FastAPI. Static build assets contain no private configuration. Source routes render a frontend source page backed by a separately authorized canonical source API; the HTML shell itself contains no protected source text. Direct page loads and new-tab receipt links must work. Add a focused span lookup to the source API so deep links do not require fetching every prior page.

Use no-store for sensitive responses, clear client state on logout/project changes, and re-fetch/revalidate receipts when opening them. Do not persist private answers/quotes in localStorage or service-worker caches. Displayed factual content comes only from reviewed claims; project overview excerpts retain their source references and rebuild status. Proposed UI-specific behavior does not settle the deferred visualization content.

## Implementation acceptance

C verifies backend import/startup and frontend build/typecheck; A/B verify their module behavior and boundary contracts. Check no cross-imports between concrete evidence/intelligence packages and no HTTP dependency inside contracts. Browser acceptance then exercises actual services, not mocked adapters. The worker specs define semantic/lifecycle cases. These folders and this document alone are not a running application.
