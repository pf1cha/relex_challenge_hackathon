# Three-worker implementation plan

Status: delivery plan revision 4, 2026-09-19. Three people implement and test A, B and C concurrently. Policy defaults remain proposals; service contract revision 3 is unchanged. Read `architecture.md` for code layout and `independent-testing.md` for standalone acceptance.

Authoritative workspace: `ssh verda`, `/mnt/relex-kai`. This document does not assert current implementation or staffing status.
This plan does not rely on another checkout's code or delivery contract.

## Source authority and scope

- `../production-behavior.md`: observable requirements, especially evidence, chronology, project access and person deletion.
- `../user-features.md`: document list, citation interaction, project visualization entry point, admin controls and associations.
- `../ai-agent-architecture.md`: selected technical direction: PostgreSQL authority, Qdrant candidates, three memory levels, separate answer/reviewer contexts, dependency invalidation and application-managed erasure.
- `../database.md`: candidate DBML, not a migration to copy verbatim. Adapt it to versioned records/spans/dependencies. Do not store erased names in purge audit logs; do not require a structured decision ledger or PostgreSQL vectors when the architecture makes statements optional and selects Qdrant.
- `../Pseudo-AI-agent.md`: background only. Do not adopt synthetic human names, HSM deployment, quasi-identifier generalization, or mapping-only erasure. Do not claim legal compliance.

Input SHA-256:

| File | SHA-256 |
| --- | --- |
| production-behavior.md | 8dee98c55acd566612dba1a65c096e5401edadc1746d77eca9175303191e6825 |
| user-features.md | 4dba75ca5b900560526dbe1aad179c1dbf6063ad8aefc9b55a4d55a0ece10a18 |
| ai-agent-architecture.md | 78610a73ef68d218b7c4083516ac76273aa042a082850649f7ffdf504a830952 |
| database.md | a0e4907edbb3b9b11b82ac4b863702e034007864de0cb46bd20da3cbb82d048c |
| Pseudo-AI-agent.md | 1350b4b900b78d322597ab9f67a4185ceaa1c7b582eb4e32fd939a5c2c825244 |

## Proposed implementation defaults

These choices make interfaces implementable. Keep them explicit in the handoff; a change requires a coordinated contract update, not three separate interpretations.

1. Separate `backend/` Python/FastAPI application and `frontend/` TypeScript browser application, with separate dependency manifests and tests. FastAPI may serve the compiled frontend for a single-origin deployment. PostgreSQL is canonical; Qdrant supplies retrieval candidates. One model provider may serve the three roles with separate contexts. Use real embeddings of discovered dimension, not a hard-coded DBML vector size. See `architecture.md` for packages, entry points and dependency direction.
2. Project admin manages membership, documents, client/employee associations and project-local person erasure. Member reads active evidence. No system-admin bypass or organization-wide erasure in this slice. A personnel association does not grant a login account access.
3. Real cookie-based login sessions, password hashes, explicit bootstrap command. No caller-supplied user headers as authentication. Production SSO is deferred.
4. Members see opaque person references initially; contacts and identity mapping are admin-only. This resolves the architecture's open rendering choice conservatively. Erased references render as `[deleted user]`.
5. Members cannot browse inactive documents. Admin may inspect current sanitized inactive sources. Old answers with invalid dependencies become unavailable; revision 3 chooses unavailable/regenerate for changed receipt versions rather than automatic remapping. Superseded decisions remain historical evidence while their sources remain active.
6. Initial import formats: UTF-8 bundled emails, text reports, transcripts. Unsupported formats fail visibly. PDF/OCR is deferred. Preserve title/file identity and source boundaries; sanitize identifying metadata as part of privacy processing.
7. Adopt proposed ingestion removal of residence addresses and non-work private discussion, preserving supported work constraints. Uncertain identity matches or uncertain sensitive spans quarantine the record with an admin recovery path; never silently merge same-name people.
8. Visualization deliverable is project selector and explicitly labeled processing/status information. Actual visualization content remains an open product decision and is not completed by this placeholder.
9. Retained raw/intermediate uploads are restricted and included in the erasure inventory. Corpus input originals outside application-managed storage are not edited. External provider retention/backups must be inventoried as limits; do not promise erasure outside controlled stores.

## Ownership: three parallel implementation slices

| Worker | Outcome | Exclusive paths |
| --- | --- | --- |
| A — evidence platform | Authorized, versioned, privacy-safe evidence and durable lifecycle jobs | `backend/app/evidence/`, `backend/app/contracts/`, `backend/migrations/`, `backend/tests/evidence/`, `backend/tests/contracts/`, `scripts/evidence/`, `docs/implementation/evidence-a.md` |
| B — knowledge and answers | Maintained memories, hybrid search, reviewed claims and history | `backend/app/intelligence/`, `backend/tests/intelligence/`, `scripts/intelligence/`, `docs/implementation/evidence-b.md` |
| C — product and integration | Working authenticated browser/admin flows and assembled application | `backend/app/api/`, `backend/app/__init__.py`, `backend/app/main.py`, `backend/app/bootstrap.py`, `backend/app/config.py`, `backend/app/worker.py`, `backend/tests/product/`, `frontend/`, `scripts/product/`, `fixtures/implementation/`, dependency manifests, `.env.example`, root `README.md`, `docs/implementation/evidence-c.md` |

These are target ownership paths; inspect the current checkout before implementation. A owns schema/contract changes; C owns startup, composition and dependency manifests (including backend packaging/test configuration). Agree independently installable per-slice test dependencies in G0. Subsequent shared dependency changes go through C and contract changes through A; no slice requires another person's running service or completed implementation. Each worker owns package initializers inside its directories. No two workers edit the same file. Specification files are coordinator-owned. No worker edits the five input docs. Do not overwrite `.env` or restore inherited deletions.

## Parallel execution and integration gates

- **G0 — shared starter before parallel implementation:** Check in importable revision 3 DTOs/protocols/errors, contract examples/conformance cases and minimal packaging with per-slice test dependencies. A owns contract files and C packaging; this bounded setup requires no completed A1 or production implementation. The prose below alone is not a completed starter. See `independent-testing.md` for readiness.
- **S-A / S-B / S-C — concurrent standalone acceptance:** All three people implement and test their real slice using substitutes at the other slices' contract boundaries. Each owns fixtures, runner and isolated resources. Tests must run without the other concrete implementations, C's production bootstrap or another person's development server. Standalone acceptance establishes each slice's behavior; G1-G4 establish the assembled product.
- **G1 — first vertical flow:** C accepts an admin upload; A persists a sanitized staged record under a job-scoped internal capability; B reads that staged version, creates memories and indexes it; A verifies dependencies and publishes the coherent version; C opens the source as a member. Staged records are never member/agent-readable. Verify outsider denial. A and B jointly validate the real durable job handler interface for G1; their standalone job tests proceed independently.
- **G2 — reviewed chat:** B supplies search and answer service; C exposes it and renders claim receipts; A supplies final eligibility validation. Run the long-record and chronology cases in Worker B's spec.
- **G3 — lifecycle:** A owns invalidation/erasure coordination, B rebuilds derived artifacts, C exposes job/retry and unavailable states. Run interruption and in-flight invalidation cases.
- **G4 — live acceptance:** C assembles evidence from A/B and runs authenticated browser workflows using real PostgreSQL, Qdrant, generation and embeddings. Each worker reviews the next worker's boundary (A reviews B eligibility; B reviews C receipt rendering; C reviews A lifecycle API) without editing their files. Unresolved failures remain explicit.

After G0, A1-A4, B1-B4 and C1-C4 proceed concurrently. No standalone test or slice handoff waits for another implementation or shared integration fixtures. G1-G4 are separate integration gates, run as real adapters become available. Shared contract changes require a coordinated version update. Coordinator resolves cross-owner changes.

## Shared contract revision 3

G0 provides these typed models/protocols with complete signatures and error semantics; A maintains them thereafter. All three slices start from the same pinned contract revision. Internal service calls receive a server-created context; public bodies and agent arguments cannot set or override it.

```text
RequestContext(user_id, session_id, project_id, role, access_revision,
               corpus_generation, privacy_generation)
EvidenceRef(project_id, original_doc_id, record_id, record_version, span_ids)
Span(span_id, ordinal, text, source_location)
Dependency(record_id, record_version, span_ids)
Memory(id, project_id, level:1|2, kind:record|topic|overview,
       text, dependencies[], generator_version, updated_at)
RecordPage(record_id, record_version, spans[], memories[], total_chunks,
           returned_chunk_ids[], next_cursor, complete, corpus_generation,
           privacy_generation)
Job(id, project_id, kind, state, stage, affected_object_ids[],
    counts, error_code?, retryable, created_at, updated_at)
Receipt(id, evidence_ref, quote, source_url)
Claim(id, text, receipt_ids[], status?, scope?, effective_at?)
Answer(id, claims[], receipts[], cannot_establish?, coverage,
       dependencies[], corpus_generation, privacy_generation)
Conversation(id, project_id, owner_user_id, title, created_at)
Message(id, conversation_id, role, text_or_answer_id, created_at)
JobCapability(job_id, project_id, lease_token, lifecycle_revision,
              allowed_record_versions[], allowed_stage)
ReviewResult(claim_id, verdict, reason_code, receipt_ids[], repair_request?)
ReviewedCandidate(claims[], receipts[], review_results[], dependencies[],
                  corpus_generation, privacy_generation, coverage)
```

`source_location` contains known original line/paragraph/message/turn/timestamp boundaries; unknown values stay null. `span_id` is a stable identifier, not a byte offset. A rewritten span has a new version and an internal provenance mapping; this does not authorize old answer receipts to use the new text. Cursor is bound to project, record version and generation; reject stale cursors. RecordPage `complete` means this cursor sequence reached the record end; answer coverage separately proves every required chunk was actually supplied to the model, not merely that a last-page cursor was requested.

Job state: `pending -> running -> completed`; failure is `failed` with a safe error code and retry capability. Stage distinguishes `received/parsed/privacy_ready/extracted/indexed/published` or erasure phases. Completed ingestion means all required artifacts published. Failed erasure leaves affected evidence unavailable. Retry resumes the same job with idempotent stage keys.

Internal ports:

```text
A: authorize(user_id, project_id, admin=False) -> RequestContext
A: read_record(ctx, record_id, cursor=None) -> RecordPage
A: read_memory(ctx, memory_id) -> Memory
A: resolve_receipt(ctx, evidence_ref) -> Receipt | unavailable
A: release_answer(ctx, conversation_id, request_id, reviewed_candidate) -> Answer | changed
A: release_overview(ctx, reviewed_candidate) -> eligible overview | changed
A: load_staged_record(job_capability, record_id, version) -> sanitized staged record
A: normalize_query(ctx, text) -> privacy-safe text and unambiguous person IDs
A: submit_upload / mutate_document / submit_person_erasure -> Job
A: canonical repository + job claim/ack/retry + publication operations
B: process_record(job_capability, record_id, version) -> staged artifacts + index evidence
B: rebuild_affected(job_capability, dependency_ids) -> staged artifacts + index evidence
B: remove_index_entries(job_capability, entry_ids) -> deletion evidence
B: search_memory(ctx, query, filters) -> scoped candidate records
B: get_decision_history(ctx, topic_id, scope, as_of) -> evidence-linked history
B: answer(ctx, question, normalized_history) -> ReviewedCandidate
C: composition root wires A/B; HTTP adapters -> services -> final release -> response
```

A's job runner invokes B's processing/rebuild handlers registered by C's composition root. B never imports A's concrete repositories or C and never controls authentication. A exposes repositories and restricted staged reads through contracts; B never writes SQL migrations. Use a durable outbox/job table: do not hold SQL transactions over model/Qdrant calls. Staged indexes are ineligible until canonical SQL publication; all reads recheck SQL. A marks revoked evidence unavailable before asynchronous rebuilding starts. B reports index replacements/removals; A verifies before publication/completion. Job capabilities bind project, job, stage and version, and cannot be supplied via public APIs or agent tools.

Eligibility is purpose-specific: `answer_evidence` requires active published sources, while `admin_source_preview` may read current sanitized inactive sources after admin authorization. Both enforce project/privacy/version checks; admin preview never makes inactive evidence eligible for agents. Draft review and final answer release use `answer_evidence`. Normalize names/contact strings in questions and conversational context before model calls; do not return identity mappings from the normalization operation. Ambiguous names prompt clarification rather than a guessed person match.

Final release has an explicit linearization point: in one short transaction A rechecks access, corpus/privacy generation and dependencies and persists the approved answer. A mutation committed before that point invalidates release. No database lock spans model calls or browser delivery; bytes already delivered cannot be recalled. All subsequent answer/source requests recheck current eligibility. Conservatively invalidate saved answers on corpus generation changes so a new correction invalidates old current-state conclusions even if their directly cited records did not change.

`release_answer` also checks that the login session is still valid, the conversation belongs to this caller/project, every released claim has a passing review bound to its exact text/receipts, and canonical receipt quotes still match. No separate route-level validate-then-save operation is allowed. Server-loaded, currently eligible history is the only history supplied to B; the client cannot submit trusted history or reviewed candidates. Scope `request_id` to caller/conversation and input hash to deduplicate a retried chat POST; reuse with different input is 409. Login/logout/session revocation applies to in-flight requests as well as the next request.

Person/document erasure is a project write barrier, described in `architecture.md`: pause new content-producing writes and reject stale job/answer publication until all prior writers and pending index operations are drained or safely fenced. Read access to unaffected evidence may continue. Never report erasure completed merely because stale content is query-ineligible while an earlier write can still recreate it.

Record/index eligibility compares each entry with SQL's published record/artifact version and input hash, not equality with the latest global corpus generation. Global revisions invalidate request snapshots and saved answers; they do not require rewriting unrelated vectors. Initial imports publish base records/chunks coherently; dependent topic/overview rebuilds are separate jobs with explicit unavailable/pending state, not a circular prerequisite for base-record publication.

Search filters: `date_from`, `date_to`, `record_type`, `original_doc_id`, `topic_id`, `person_id`. Date bounds use source event date; unknown dates do not match bounded dates. Public search and agent tools share this service. No memory-level selector. Qdrant text is never returned without canonical eligibility validation.

Receipt example:

```json
{"id":"receipt-1","evidence_ref":{"project_id":"p1","original_doc_id":"d1","record_id":"r1","record_version":2,"span_ids":["s7"]},"quote":"The October launch is agreed.","source_url":"/projects/p1/sources/r1?version=2&span=s7"}
```

HTTP routes owned by C (all project routes authorize server-side):

| Route | Contract |
| --- | --- |
| `POST /api/login`, `POST /api/logout`, `GET /api/me` | Session lifecycle; C adapters call A authentication service |
| `GET /api/projects` | Membership-filtered `{items:[{id,name,role}]}` |
| `GET /api/projects/{p}/documents` | Visible document metadata and processing state |
| `POST /api/projects/{p}/documents` | Admin multipart file/type; 202 Job |
| `POST /api/projects/{p}/documents/{id}/activate` or `/deactivate`; `DELETE /api/projects/{p}/documents/{id}` | Admin lifecycle; 202 Job |
| `POST /api/projects/{p}/search` | `{query,filters}` -> `{items:[{record_id,description,snippet,total_chunks}]}` |
| `GET /api/projects/{p}/records/{id}?cursor=...` | RecordPage |
| `GET /api/projects/{p}/sources/{id}?version=...&span=...&cursor=...` | Authorized source page centered on the cited span; explicit admin-preview purpose for inactive sources |
| `GET /projects/{p}/sources/{id}?version=...&span=...` | Authorized current sanitized source with highlighted span |
| `POST /api/projects/{p}/conversations`; `GET /api/projects/{p}/conversations` | Create/list caller-owned project conversations |
| `GET /api/projects/{p}/conversations/{id}/messages` | Owner-only messages; invalid answers are unavailable placeholders |
| `POST /api/projects/{p}/chat` | `{question,conversation_id,request_id}` -> Answer after review and atomic release/persistence |
| `GET /api/projects/{p}/answers/{id}` | Owner-scoped saved answer, current eligibility rechecked |
| `GET /api/projects/{p}/status` | Eligible document/processing counts and generation |
| `GET /api/projects/{p}/overview` | Grounding-reviewed claims/receipts and rebuild state; pending/failure exposes no unchecked factual prose |
| `GET /api/projects/{p}/answers/{id}/receipts/{receipt_id}` | Owner-scoped, current answer/source eligibility; exact stored receipt or 410, never silently retarget a claim |
| `GET /api/projects/{p}/filters` | Eligible record types/topics/safe document labels and opaque personnel IDs; no identity mapping |
| `GET/POST /api/projects/{p}/members`; `DELETE /api/projects/{p}/members/{user_id}` | Admin list/assign role/remove membership |
| `GET/POST /api/projects/{p}/people`; `POST /api/projects/{p}/people/{id}/erase` | Admin project-local identity associations and erasure Job |
| `GET /api/projects/{p}/jobs/{id}`; `POST /api/projects/{p}/jobs/{id}/retry` | Admin safe job status/retry |
| `GET /api/projects/{p}/jobs` | Admin paginated job discovery after browser reload |

Errors: 401 unauthenticated; 403 insufficient role; 404 inaccessible/missing resource for nonmembers without revealing existence; 409 changed generation/stale cursor; 410 previously accessible source/answer unavailable; 422 invalid input; 503 provider/dependency failure. Standard body `{error:{code,message,retryable}}` without raw provider errors or personal data. Mutations require CSRF protection. Never stream factual draft text before review.

Lists use `{items,next_cursor}`; cursors are opaque and project/role scoped. Document lists include record IDs or a record-list link so bundled documents can be opened without search. Member/status/filter responses include only eligible records; admin operational counts may include inactive/failed jobs but never raw content. For inactive source previews, the server derives purpose from authenticated admin role and document state; callers cannot elevate privileges with a purpose parameter.

## Overall completion evidence

Each worker records commands, exit status, relevant IDs/versions, observed outcomes and unresolved failures in its evidence file. Never record credentials or raw personal data in traces. Standalone tests may substitute other slices through shared contracts. B's live acceptance requires real model/reviewer/embedding and Qdrant calls. End-to-end G1-G4 require all real slices, real services and actual browser interactions; fake embeddings or a mock reviewer cannot pass those gates.

Before standalone verification, each person checks their own required services/resources with synthetic data. Before G1-G4, C checks the assembled service/model availability and permitted compute allocation/browser route. Existing old delivery evidence is not current proof. Do not run services/heavy inference on login nodes or assume authorization to send the private corpus to a new provider. Default to synthetic fixtures. Record provider, model ID and embedding dimension safely. Identify unavailable prerequisites precisely rather than fabricating success.

Independent slice handoff requires S-A, S-B or S-C in `independent-testing.md` with cross-slice claims marked integration pending. Overall product success additionally requires all acceptance cases with real adapters and G1-G4. The visualization content deferral and external retention limits remain explicit. This task produces specs only; it does not authorize deployment, dispatch, destructive corpus changes, or publication.
