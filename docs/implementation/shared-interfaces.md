# Shared service interfaces

Contract revision 5 — 2026-09-19. Specification for implementation in `/mnt/relex-kai`. This document defines the A/B/C boundaries; [http-api.md](http-api.md) defines their public HTTP projection. It does not claim these interfaces are already implemented.

Revision 5 adds durable staged-artifact reload and recovery semantics to revision 4. Revision 4 replaced the shorthand revision 3 signatures. It makes session authorization, chat reservations, pagination, staged artifacts, index-operation acknowledgement and fixture behavior explicit. Existing product requirements remain; the proposed role/privacy defaults in the implementation README remain proposals. A owns shared DTOs/protocols/errors; C owns HTTP schemas and composition. Changes to signatures or semantics require a contract revision and coordinated adapter updates.

## Verification policy: real services

Verification follows [real-service-verification.md](real-service-verification.md). Run the actual implementation against real PostgreSQL, Qdrant, configured model/reviewer/embedding services, FastAPI and a browser wherever the required operation uses them. Synthetic input documents are encouraged; fake service responses are not acceptance evidence.

Contract tests, schema examples and fixture-service scenarios below are development aids. They may establish implementation readiness but cannot mark product behavior verified. Cross-slice live checks stay pending until real adapters are available. Independent code handoff remains allowed, explicitly labeled implementation-ready rather than live-verified; missing services are reported as blockers, never replaced by a mock pass.


## 1. Ownership and dependency injection

| Interface | Implemented by | Used by | Independent test substitute |
| --- | --- | --- | --- |
| Auth, Project, Document, Source, Administration, Conversation services | A | C | C's in-memory scenario services |
| EvidenceReader, RetrievalRepository, ArtifactRepository | A | B | B's canonical fixture repository |
| JobCoordinator and IndexOperationLedger | A | A runner and B handlers | B's fixture job/operation ledger |
| IntelligenceService and MaintenanceHandlers | B | C routes and A job runner | A/C controlled B services |
| PrivacyDetector | Configured adapter injected by C; protocol owned by A | A preprocessing | A deterministic detector |
| Application factory and HTTP adapters | C | Browser | Real C application with fixture services |

All service methods below are asynchronous unless explicitly pure. Arguments use typed DTOs, not arbitrary dictionaries or SQL. A method returning `T` either returns that type or raises `DomainError`; no undocumented `None` or exception strings. Constructors receive dependencies; imports perform no connections, migrations or production configuration reads.

`Services` contains `auth, projects, documents, sources, administration, conversations, intelligence` implementing these protocols. C's `create_app(services: Services, settings: HttpSettings)` registers the actual routes without importing production bootstrap. `HttpSettings` contains trusted origins, cookie transport settings, upload limit and request timeout; it contains no database/model credentials. Production bootstrap constructs real services; fixture composition constructs substitutes. Neither the browser nor an HTTP body can select fixture mode.

A's worker accepts `MaintenanceHandlers` by registration. B receives A's repository ports in its constructor. Neither A nor B imports the other's concrete module. C may generate OpenAPI and build the UI from fixture composition before either real implementation exists.

### Database transport

A implements canonical repositories through a direct PostgreSQL driver connection to the local server on the backend host (`verda` initially). See [architecture.md](architecture.md) for connection settings and process ownership. These service/repository protocols are Python call boundaries; they do not require a database HTTP API. C's browser-facing HTTP API remains the authorized entry point. No `PG*` setting, database credential or raw SQL is a public DTO field. A owns database access for both backend processes; B and C use its injected interfaces.

## 2. Type and serialization rules

The following `text` blocks are schema notation, not Python source.

- `Id`: opaque nonempty string, at most 128 characters; clients must not infer authorization or chronology from it.
- `Version`: positive integer. `Revision` and counts: nonnegative integers. No booleans accepted as integers.
- `Instant`: RFC 3339 timestamp with offset, serialized to UTC `Z`. `Date`: `YYYY-MM-DD`.
- `Digest`: lowercase SHA-256 hexadecimal string. Hash algorithm/version is part of the contract.
- `T?`: required field whose value may be null. `field?: T`: optional input field. Output DTOs include all listed fields, including nullable fields.
- Enum values are case-sensitive lower snake case. Arrays preserve order; IDs within an ID set are unique.
- `PageRequest {cursor?: string, limit?: integer}`: default limit 25, range 1–100. `Page<T> {items: T[], next_cursor: string?}`. A null cursor means no more items.
- Cursors are opaque, integrity-protected and bound to operation, project, caller/role, filters, sorting and relevant versions. Resume with the same query; mismatches yield `stale_cursor`. Stable list order is `created_at, id` ascending unless explicitly specified.
- Unknown input fields, invalid ranges and invalid enum values fail validation. Public clients cannot submit contexts, identities, capabilities, histories, review results or internal index payloads.
- Public text is plain text, never trusted HTML. Raw exception/provider messages are not public fields.
- Pure `make_entry_id(project_id, record_id, record_version, chunk_id, input_hash, embedding_model, embedding_dimension)` returns UUIDv5 using the standard URL namespace and name `relex:entry:v4:` followed by compact JSON of those ordered arguments. All callers use A's shared implementation; IDs contain no names/contact strings.

```text
Role = member | admin
RecordType = email | transcript | report | specification
Purpose = answer_evidence | admin_source_preview

Snapshot {corpus_generation: Revision, privacy_generation: Revision}
SessionPrincipal {user_id: Id, session_id: Id, expires_at: Instant}
RequestContext {
  user_id: Id, session_id: Id, project_id: Id, role: Role,
  access_revision: Revision, corpus_generation: Revision,
  privacy_generation: Revision
}
SourceTime {
  value: string?, precision: unknown | year | month | day | instant,
  timezone: string?
}
```

`SourceTime.value` is null for unknown, `YYYY`/`YYYY-MM`/`Date` for date precision, or an offset timestamp for instant. Never manufacture midnight or a timezone for unknown data. Date filtering uses source event date: a partial date matches a bounded range only if its entire possible interval is within that range. Unknown dates do not match bounded queries.

`RequestContext` is created by A from a valid session and current membership. It is a snapshot, not permanent permission. Every canonical operation rechecks session/access and applicable eligibility; publication/release additionally checks generations atomically. A context constructed by a fixture is permitted only in tests. All IDs supplied to a method must belong to its context's project.

## 3. Public data types

These are the exact DTO families C may expose. Additional internal fields must be removed by explicit response models.

```text
Me {user_id: Id, display_name: string, csrf_token: string, expires_at: Instant}
Project {id: Id, name: string, role: Role}
Document {
  id: Id, project_id: Id, title: string, record_type: RecordType,
  ai_status: active | inactive,
  processing_state: pending | running | completed | failed,
  record_count: integer, records_url: string, latest_job_id: Id?,
  created_at: Instant, updated_at: Instant
}
RecordSummary {
  record_id: Id, original_doc_id: Id, record_version: Version,
  title: string, record_type: RecordType, source_time: SourceTime,
  total_chunks: integer
}
SourceLocation {
  line_start: integer?, line_end: integer?, paragraph: integer?,
  message_ordinal: integer?, turn_ordinal: integer?, timestamp_label: string?
}
Span {span_id: Id, ordinal: integer, text: string, source_location: SourceLocation}
EvidenceRef {
  project_id: Id, original_doc_id: Id, record_id: Id,
  record_version: Version, span_ids: Id[]
}
Dependency {
  record_id: Id, record_version: Version, span_ids: Id[]
}
RecordPage {
  record: RecordSummary, spans: Span[], returned_chunk_ids: Id[],
  total_chunks: integer, next_cursor: string?, complete: boolean,
  snapshot: Snapshot
}
SourcePage {
  record: RecordSummary, spans: Span[], highlighted_span_ids: Id[],
  next_cursor: string?, previous_cursor: string?, snapshot: Snapshot
}
Receipt {
  id: Id, evidence_ref: EvidenceRef, quote: string, source_url: string,
  source_title: string, record_type: RecordType, source_time: SourceTime,
  source_locations: SourceLocation[]
}
Claim {
  id: Id, text: string, receipt_ids: Id[],
  status: suggestion | commitment | superseded | corrected | conflict | unknown | null,
  scope: string?, effective_at: SourceTime?
}
Coverage {
  state: complete | partial | insufficient,
  records: RecordCoverage[], limitations: Limitation[]
}
RecordCoverage {
  record_id: Id, record_version: Version, total_chunks: integer,
  supplied_chunk_ids: Id[], complete: boolean
}
Limitation {
  code: no_evidence | unread_chunks | history_incomplete | conflicting_evidence |
        budget_exhausted | ambiguous_person | unknown_effective_time,
  record_ids: Id[]
}
Answer {
  id: Id, conversation_id: Id, request_id: Id,
  claims: Claim[], receipts: Receipt[], coverage: Coverage,
  cannot_establish: no_evidence | incomplete_coverage | unresolved_conflict |
                    ambiguous_person | review_rejected | null,
  snapshot: Snapshot, created_at: Instant
}
Conversation {
  id: Id, project_id: Id, owner_user_id: Id, title: string,
  created_at: Instant, updated_at: Instant
}
Message {
  id: Id, conversation_id: Id, role: user | assistant,
  state: available | pending | unavailable | failed,
  text: string?, answer_id: Id?, unavailable_reason: string?,
  created_at: Instant
}
Job {
  id: Id, project_id: Id, kind: JobKind, state: JobState, stage: JobStage,
  counts: map<string, integer>, error_code: string?, retryable: boolean,
  created_at: Instant, updated_at: Instant
}
JobKind = ingest | activate | deactivate | delete_document | erase_person |
          rebuild_aggregate | reconcile
JobState = pending | running | completed | failed
JobStage = received | parsed | privacy_ready | extracted | indexed | published |
           invalidating | inventory | draining | sanitizing | rebuilding |
           removing_index | verifying | done
ProjectStatus {
  project_id: Id, eligible_documents: integer, eligible_records: integer,
  operational_job_counts: map<JobState, integer>?,
  write_barrier: boolean, snapshot: Snapshot
}
Overview {
  state: pending | ready | failed | unavailable,
  id: Id?, claims: Claim[], receipts: Receipt[], coverage: Coverage?,
  snapshot: Snapshot, error_code: string?
}
Member {user_id: Id, display_name: string, role: Role, granted_at: Instant}
Person {
  id: Id, display_name: string, kind: client | employee,
  contacts: Contact[], state: active | erasing
}
Contact {kind: email | phone | postal_address, value: string}
FilterOptions {
  record_types: RecordType[], documents: Option[], topics: Option[], people: Option[]
}
Option {id: Id, label: string}
```

`Document.title` and source metadata are sanitized. Members list only active published documents/records; admins may list current sanitized inactive documents and safe processing metadata. Deleted documents are absent. Only eligible records contribute to member-visible counts and record lists. An ingestion job completes only after all its required records/artifacts are published; aggregate rebuilds are separate and do not block coherent base-record publication.

Span ordinals are zero-based; displayed line/paragraph/message/turn locations are one-based. A span ID is stable across privacy edits, but its enclosing record version changes; deleted spans never become different evidence under the old version.

`RecordPage` emits whole chunk descriptors' source spans in order, deduplicating overlap within a page. `complete` means this page reaches the end, not proof all earlier pages reached the model. `Coverage` records actual supplied chunk IDs. A centered `SourcePage` may start mid-record and is never used as proof of complete record reading.

Each receipt covers one or more ordered contiguous spans from one record/version. `quote` equals those entire published sanitized span texts joined by a single LF, without trimming or normalization. Noncontiguous evidence uses separate receipts. No arbitrary character offsets or silent old-version remapping. `source_url` is a relative in-app URL generated/validated by A; no model-supplied external URL.

Every factual clause is in `claims` and has at least one receipt. Unknown/conflict wording still cites the evidence it describes. Operational inability messages use `cannot_establish` and fixed UI text, not unchecked generated narrative. `claims=[]` is valid for inability; `receipts=[]` then follows. Output receipts contain only IDs used by released claims. Commitment prose includes supported proposer, agreeing parties, owner, due date, scope and conditions; missing requested details are explicitly unknown. These may be expressed in claim text without imposing a fixed decision-ledger schema. Dependencies include relevant counterevidence and transitive source records, not only displayed receipts.

User messages contain normalized privacy-safe text; assistant messages reference an answer and have `text=null`. Pending/failed user turns remain clearly marked. Invalidated assistant messages expose neither old text nor answer ID, only an unavailable reason. Conversation titles use fixed safe defaults initially; generated titles are not required. `Person` and contacts are admin-only; personnel associations never confer login membership. Filter people use opaque IDs/labels, never the identity mapping.

## 4. Errors

`DomainError {code: ErrorCode, retryable: boolean}` carries a code and safe structured identifiers internally. C maps it to `{error:{code,message,retryable}}` with fixed message templates. Error handling never serializes internal payloads.

| Code | HTTP | Retryable | Meaning |
| --- | --- | --- | --- |
| unauthenticated | 401 | false | Missing, expired or revoked session; includes failed login |
| forbidden | 403 | false | Known project member lacks required role |
| csrf_failed | 403 | false | Missing/incorrect CSRF proof or untrusted origin |
| not_found | 404 | false | Missing object or caller has no project/object ownership |
| evidence_changed | 409 | true | Snapshot changed during retrieval/release; start a new attempt |
| stale_cursor | 409 | true | Restart pagination with a fresh cursor |
| write_barrier | 409 | true | Project cleanup blocks content-producing writes |
| request_in_progress | 409 | true | Same chat request is already being processed |
| idempotency_conflict | 409 | false | Same key with different input |
| last_admin | 409 | false | Mutation would remove the last project admin |
| ambiguous_person | 409 | false | Administrative association needs disambiguation |
| source_unavailable / answer_unavailable | 410 | false | Authorized object is now ineligible |
| invalid_input / unsupported_format | 422 | false | Invalid input or unsupported upload |
| upload_too_large | 413 | false | Upload exceeds configured limit |
| provider_unavailable / dependency_unavailable | 503 | true | Required service cannot complete work |
| contract_violation | 500 | false | Invalid implementation output; withhold it |
| internal_error | 500 | false | Unexpected application failure; safe response only |

`lease_lost, capability_denied, index_outcome_unknown` are worker-only errors, never public error messages from an agent. Unknown remote write outcomes remain pending/failed and cannot be converted to successful cancellation. A revoked/nonmember caller receives 404 before evidence-specific 410/409 so object existence is not disclosed.

## 5. A services consumed by C

### Authentication and project context

```text
AuthService.login(email: string, password: string) -> LoginResult
AuthService.authenticate(session_token: string) -> SessionPrincipal
AuthService.validate_csrf(principal: SessionPrincipal, token: string) -> None
AuthService.logout(principal: SessionPrincipal) -> None
AuthService.me(principal: SessionPrincipal) -> Me
ProjectService.list_projects(principal: SessionPrincipal, page: PageRequest) -> Page<Project>
ProjectService.authorize(principal: SessionPrincipal, project_id: Id,
                         required_role: Role = member) -> RequestContext
LoginResult {session_token: string, me: Me}
```

`LoginResult.session_token` is internal transport data: C sets a cookie; it never returns the token in JSON. A stores hashed session credentials, validates expiry/user activity and implements revocation. C enforces transport origin/CSRF policy before state-changing route calls. A validates the session-bound CSRF token through the method above. Membership/access revisions are checked by A even after C has obtained a context.

### Project data and lifecycle

```text
DocumentService.list_documents(ctx, page: PageRequest) -> Page<Document>
DocumentService.list_records(ctx, document_id: Id, page: PageRequest) -> Page<RecordSummary>
DocumentService.submit_upload(ctx, upload: UploadInput) -> Job
DocumentService.mutate_document(ctx, document_id: Id,
                               action: activate | deactivate | delete) -> Job
SourceService.read_record(ctx, record_id: Id, page: PageRequest) -> RecordPage
SourceService.read_source(ctx, request: SourceRequest) -> SourcePage
SourceService.get_status(ctx) -> ProjectStatus
SourceService.get_overview(ctx) -> Overview
SourceService.get_filters(ctx) -> FilterOptions
AdministrationService.list_members(ctx, page: PageRequest) -> Page<Member>
AdministrationService.set_member(ctx, user_id: Id, role: Role) -> Member
AdministrationService.remove_member(ctx, user_id: Id) -> None
AdministrationService.list_people(ctx, page: PageRequest) -> Page<Person>
AdministrationService.associate_person(ctx, input: PersonInput) -> Person
AdministrationService.erase_person(ctx, person_id: Id) -> Job
AdministrationService.list_jobs(ctx, page: PageRequest) -> Page<Job>
AdministrationService.get_job(ctx, job_id: Id) -> Job
AdministrationService.retry_job(ctx, job_id: Id) -> Job

UploadInput {filename: string, record_type: RecordType, content: bytes}
SourceRequest {record_id: Id, version: Version, span_id: Id, cursor?: string, limit?: integer}
PersonInput {
  person_id?: Id, display_name: string, kind: client | employee, contacts: Contact[]
}
```

`ctx` is always `RequestContext` in this section. Mutations, people/members and jobs require admin. `set_member` assigns/replaces the project's member/admin role for an existing login user; account creation remains an explicit bootstrap operation. `associate_person` updates the named project identity or creates a new one; it never merges by name alone. Duplicate ambiguous contacts require explicit disambiguation. Erasure targets an exact person ID, not a free-text name.

The upload is bounded by C before materializing bytes; A independently validates supported UTF-8 content. Raw bytes and filename enter A's restricted preprocessing inventory, not B/C logs. `202 Job` means accepted, not published or erased. Job creation plus invalidation/barrier changes commit before the mutation returns. Duplicate active lifecycle commands for the same target/action return the active job; incompatible target mutations return `write_barrier` while cleanup is active. Retry resumes the same failed retryable job; a completed job returns unchanged, a nonretryable failed job yields `invalid_input`.

Source preview purpose is derived server-side: `read_record` always uses active answer evidence; `read_source` may allow current sanitized inactive content for admins. The public caller cannot specify purpose. The requested exact record version and span must resolve or return unavailable. Browser source pagination remains centered initially and uses source-bound cursors thereafter.

Only ready, grounding-reviewed overview claims are returned. All other overview states have empty claims/receipts. Operational counts are null for members. Authorization changes may continue during an erasure barrier; uploads, associations, conversations/chat persistence and ordinary publication cannot.

### Conversations, retry reservations and final release

```text
ConversationService.create(ctx, title?: string) -> Conversation
ConversationService.list(ctx, page: PageRequest) -> Page<Conversation>
ConversationService.messages(ctx, conversation_id: Id, page: PageRequest) -> Page<Message>
ConversationService.begin_chat(ctx, input: ChatInput) -> BeginChatResult
ConversationService.release_answer(ctx, attempt: ChatAttempt,
                                   candidate: ReviewedCandidate) -> Answer
ConversationService.fail_chat(ctx, attempt: ChatAttempt, code: ErrorCode) -> None
ConversationService.get_answer(ctx, answer_id: Id) -> Answer
ConversationService.get_receipt(ctx, answer_id: Id, receipt_id: Id) -> Receipt

ChatInput {question: string, conversation_id: Id, request_id: Id}
BeginChatResult =
  {state: replay, answer: Answer}
  | {state: ready, attempt: ChatAttempt, input: AnswerInput}
ChatAttempt {
  attempt_id: Id, request_id: Id, conversation_id: Id,
  input_hash: Digest, lease_token: string, deadline: Instant
}
AnswerInput {
  question: NormalizedText, history: HistoryTurn[], request_id: Id,
  conversation_id: Id, deadline: Instant
}
NormalizedText {text: string, person_ids: Id[], ambiguous: boolean}
RuntimeLimits {
  answer_search_rounds: integer, repair_search_rounds: integer,
  reviewer_passes: integer, reviewer_search_rounds: integer,
  tool_calls_per_phase: integer, pages_per_phase: integer,
  source_tokens_per_phase: integer, request_deadline_seconds: integer
}
HistoryTurn {message_id: Id, role: user | assistant, text: string}
```

A verifies conversation ownership/project before B is called. Normalize incoming question and server-loaded eligible history before any provider call. An ambiguous person query keeps the unresolved name out of provider input and sets `ambiguous=true`; B returns a fixed clarification outcome without guessing an identity. User-supplied history is rejected. History provides conversational context only.

`begin_chat` durably reserves `(user_id, conversation_id, request_id)` and binds it to the original input using a keyed digest stored in A's restricted inventory. It stores one normalized pending user message. The original question is not logged or passed to B. Reusing the key with different input fails; a matching running request returns `request_in_progress`; a released request returns the saved answer only after current eligibility checks. An invalidated saved answer returns `answer_unavailable`, not old content.

A retryable failed/expired attempt may be retried with the same key and input: issue a new lease token, reload/normalize current history and use a fresh context snapshot. The old attempt cannot release. Never permit two completed turns for one key. Erasure inventories pending request/input metadata as well as messages. A write barrier prevents reservation/release; late attempts cannot persist after their lease/snapshot is invalidated.

`release_answer` is one short transaction: revalidate session, conversation ownership, attempt lease/deadline, access/snapshot, dependencies, receipts, review binding and then persist the answer/assistant turn and mark the request complete. No route-level validate-then-save sequence. The commit is the release point; a prior mutation causes failure. C returns only the resulting `Answer`. `fail_chat` may only transition the matching active attempt and cannot restore erased content; C preserves the original failure if cleanup reporting itself fails.

## 6. A evidence/retrieval ports consumed by B

```text
Memory {
  id: Id, project_id: Id, level: 1 | 2, kind: record | topic | overview,
  text: string, dependencies: Dependency[], generator_version: string,
  updated_at: Instant
}
MemoryPage {record_page: RecordPage, memories: Memory[]}
WorkReadContext {
  project_id: Id, job_id: Id, capability_id: Id, snapshot: Snapshot
}
ReadContext = RequestContext | WorkReadContext
SearchFilters {
  date_from?: Date, date_to?: Date, record_type?: RecordType,
  original_doc_id?: Id, topic_id?: Id, person_id?: Id
}
SearchInput {query: string, filters: SearchFilters, page: PageRequest}
CandidateRef {
  entry_id: Id, record_id: Id, record_version: Version, chunk_id: Id,
  input_hash: Digest, rank: integer
}
CanonicalCandidate {
  candidate: CandidateRef, record: RecordSummary, snippet: string, span_ids: Id[]
}
CandidateCheck {eligible: CanonicalCandidate[], rejected_entry_ids: Id[]}
HistoryQuery {topic_id: Id, scope: string, as_of: SourceTime?}
HistoryEvent {
  id: Id, topic_id: Id, scope: string,
  kind: suggestion | commitment | replacement | cancellation | correction |
        reinstatement | conflict,
  text: string, source_time: SourceTime, effective_time: SourceTime,
  learned_at: Instant, evidence: EvidenceRef[], prior_event_ids: Id[],
  review_state: pending | passed | failed
}
HistoryPage {items: HistoryEvent[], next_cursor: string?, coverage: Coverage}

EvidenceReader.read_record(ctx: ReadContext, record_id: Id, page: PageRequest) -> MemoryPage
EvidenceReader.read_memory(ctx: ReadContext, memory_id: Id) -> Memory
EvidenceReader.expand_context(ctx: ReadContext, ref: EvidenceRef,
                              before: integer = 2, after: integer = 2) -> SourcePage
EvidenceReader.normalize_query(ctx: ReadContext, text: string) -> NormalizedText
EvidenceReader.make_receipt(ctx: ReadContext, ref: EvidenceRef) -> Receipt
RetrievalRepository.lexical_candidates(ctx: ReadContext, normalized_query: string,
                                      filters: SearchFilters, limit: integer) -> CandidateRef[]
RetrievalRepository.validate_candidates(ctx: ReadContext,
                                       candidates: CandidateRef[],
                                       filters: SearchFilters) -> CandidateCheck
RetrievalRepository.read_history(ctx: ReadContext, query: HistoryQuery,
                                 page: PageRequest) -> HistoryPage
```

`limit` is 1–100; context expansion before/after is 0–20 spans and may report more pages. Query length limits are in the HTTP specification and also enforced for agent calls. B's agent tool wrapper binds contexts and budgets; the model can supply only query/filter/record/topic/span arguments, never a context or arbitrary IDs from other projects.

`WorkReadContext` is issued by A for an active job's published-snapshot reads only. It cannot read unpublished input; that uses the separate capability port below. It has no user impersonation or admin preview permission. Both kinds of read context enforce current active canonical versions. Work reads fail if dependencies/snapshot change.

Lexical results and Qdrant results carry IDs/hashes only across the candidate boundary. B fuses ranks, then A validates versions, active/privacy status, project and every filter before returning canonical text. Rejected entries are internal telemetry only, not leaked result counts. Unrelated vectors remain eligible when a global generation increments if their canonical version/hash is unchanged; an in-flight request using an old snapshot must restart.

Memory summaries never independently establish claim support. `make_receipt` loads canonical full span text and constructs the relative source link. Generated review/answer text cannot dictate its quote. History retains source/effective/learned time separately; only passed consequential relations establish replacements/corrections, and B still rereads evidence. HistoryEvent is a service DTO, not a requirement for a fixed decision-ledger or graph database; A may persist evidence-linked prose/metadata and produce this view. Work-context normalization returns only sanitized text/IDs and never grants access to identity mappings.

## 7. B services consumed by C and A

```text
SearchHit {
  record: RecordSummary, description: string, snippet: string,
  matched_span_ids: Id[]
}
SearchPage {items: SearchHit[], next_cursor: string?, snapshot: Snapshot}
ReviewResult {
  claim_id: Id, verdict: pass | fail,
  reason_code: supported | missing_support | attribution_mismatch |
               proposal_as_agreement | missing_condition | stale_as_current |
               citation_mismatch | incomplete_coverage,
  receipt_ids: Id[], repair_request: string?, candidate_digest: Digest
}
ReviewedCandidate {
  claims: Claim[], receipts: Receipt[], dependencies: Dependency[],
  coverage: Coverage,
  cannot_establish: no_evidence | incomplete_coverage | unresolved_conflict |
                    ambiguous_person | review_rejected | null,
  snapshot: Snapshot, review_results: ReviewResult[],
  candidate_digest: Digest, omission_proof: OmissionProof?
}
OmissionProof {
  reviewed: ReviewedPayload, review_results: ReviewResult[], reviewed_digest: Digest
}
ReviewedPayload {
  claims: Claim[], receipts: Receipt[], dependencies: Dependency[],
  coverage: Coverage,
  cannot_establish: no_evidence | incomplete_coverage | unresolved_conflict |
                    ambiguous_person | review_rejected | null,
  snapshot: Snapshot
}

IntelligenceService.search_memory(ctx: RequestContext, input: SearchInput) -> SearchPage
IntelligenceService.get_decision_history(ctx: ReadContext, query: HistoryQuery,
                                        page: PageRequest) -> HistoryPage
IntelligenceService.answer(ctx: RequestContext, input: AnswerInput) -> ReviewedCandidate
```

C passes the raw search query to `search_memory`; B first invokes A's normalization port. `answer` accepts only A-produced `AnswerInput`. All later agent-generated search queries also pass through normalization before embedding/provider calls. Search cursors bind normalized query, filters and snapshot; results use reciprocal-rank fusion, unique parent records and deterministic tie-breaking by record ID. Descriptions are discovery metadata; snippets are canonical excerpts. B must preserve lexical-only hits. Agent and UI search use this same service.

Candidate digest is SHA-256 of the UTF-8 compact JSON object containing exactly `claims, receipts, dependencies, coverage, cannot_establish, snapshot`. Serialize keys recursively sorted, `ensure_ascii=false`, no whitespace separators, no NaN/floats in these DTOs; preserve array order and text bytes without Unicode normalization. Exclude `retrieval_review`, `review_results`, `omission_proof` and the digest field itself. Each review result binds this digest. Changing included values requires a new review except for the verified omission-only projection described next.

For a nonempty candidate, every released claim has a passing result and exact receipt coverage. Without omission, the results bind the final candidate digest. With omission, A recomputes the proof's reviewed digest, checks passed surviving claims/receipts are identical, and rejects any added or edited claim/receipt. Dependencies, snapshot, coverage and cannot_establish must stay identical; only failed claims and their unused receipts may be removed. The final candidate digest is recomputed, but the original review results retain the reviewed digest rather than pretending the reviewer saw a different object. Every released claim must map to a passing proof result; unresolved failed claims cannot survive. A recomputes the digest and quotes; B owns semantic review quality. B's tool-free reviewer uses a separate context, receives no answer-agent private reasoning, and evaluates the exact retrieval packet assembled by the answer agent. It returns structured retrieval sufficiency and per-claim feedback; only the answer agent may retrieve or rewrite. If B rewrites any surviving claim/receipt after review, it must obtain a fresh review within the allowed pass budget. B may omit failed claims without another model call only when it retains the original reviewed candidate as internal proof, preserves each surviving claim and its receipts byte-for-byte, and A verifies that the released candidate is a subset. The proof and subset rule above are mandatory; otherwise return empty inability. Provider/reviewer failure raises `provider_unavailable`, never a verified response. Inability-only candidates have no factual claims/receipts and may have no review results.

Initial answering permits three search rounds, up to two answer-agent repair rounds, and three tool-free reviewer passes. Each answer/repair phase additionally requires finite configured tool-call, page and source-token caps, plus a request-wide deadline. This contract does not invent numerical values absent from the source specs: G0 supplies one shared `RuntimeLimits` configuration and fixtures run with explicit small values. Each search/read consumes its phase's caps; no hidden reset or unbounded pagination. Model-context limits may lower these caps. Deadline/provider failure returns a safe error; budget exhaustion may return only supported reviewed partial content with explicit coverage.

## 8. Job capabilities and staged artifact contracts

These are internal worker contracts. Nothing in this section is accepted over public HTTP or exposed to an agent as a callable mutation tool.

```text
RecordVersionRef {record_id: Id, record_version: Version}
JobCapability {
  capability_id: Id, job_id: Id, project_id: Id, lease_token: string,
  lifecycle_revision: Revision, allowed_stage: JobStage,
  allowed_record_versions: RecordVersionRef[], publication_generation: Revision,
  expires_at: Instant
}
StagedRecord {
  project_id: Id, original_doc_id: Id, record_id: Id, record_version: Version,
  record_type: RecordType, title: string, source_time: SourceTime,
  spans: Span[], person_ids: Id[], duplicate_of: Id?
}
SpanSlice {span_id: Id, start: integer, end: integer}
ChunkDescriptor {
  id: Id, record_id: Id, record_version: Version, ordinal: integer,
  slices: SpanSlice[], level1_memory_id: Id, level2_memory_id: Id,
  input_hash: Digest
}
IndexEntry {
  id: Id, project_id: Id, original_doc_id: Id, record_id: Id,
  record_version: Version, chunk_id: Id, span_ids: Id[],
  topic_ids: Id[], person_ids: Id[], source_time: SourceTime,
  publication_generation: Revision,
  input_hash: Digest, embedding_model: string, embedding_dimension: integer
}
ArtifactBatch {
  batch_id: Id, job_id: Id, project_id: Id,
  memories: Memory[], chunks: ChunkDescriptor[],
  proposed_history: HistoryEvent[], index_entries: IndexEntry[],
  dependencies: Dependency[]
}
RebuildPlan {
  id: Id, project_id: Id, record_versions: RecordVersionRef[],
  memory_ids: Id[], obsolete_entry_ids: Id[], dependencies: Dependency[],
  snapshot: Snapshot
}
MaintenanceResult {
  batch_id: Id?, operation_ids: Id[], changed_entry_ids: Id[],
  removed_entry_ids: Id[], unchanged_entry_ids: Id[]
}
StagedArtifacts {
  artifact_key: string, batch: ArtifactBatch,
  lifecycle_revision: Revision, publication_generation: Revision
}
OverviewCandidate {memory_id: Id, candidate: ReviewedCandidate}
```

Chunk slice offsets are zero-based Unicode code points, half-open, inside canonical span text; they only describe chunk overlap and are never receipt locations. B chunks within one record. Concatenate the referenced slices in source order separated by LF for chunk text. Embedding input is exactly `level1.text + "\n\n" + level2.text + "\n\n" + chunk_text` encoded UTF-8. `input_hash` hashes these bytes. Repeated changed summaries therefore change all affected inputs.

Entry IDs are immutable UUID strings suitable for Qdrant, allocated by the shared pure `make_entry_id` function. A retry reuses the same ID; another version/model cannot overwrite it. Qdrant payload contains only `IndexEntry` fields, never original names/contact mappings or raw input. Vectors stay B-owned; A receives descriptors/hash/model/dimension and durable operation evidence.

A assigns a monotonically reserved publication generation to a processing job, carried by its capability and staged index descriptors as lineage metadata. A reserved generation does not mean published; canonical record/version/hash checks decide eligibility. The project's corpus revision still advances monotonically at each mutation/publication commit and must never be assigned backwards when jobs finish out of reservation order. Unrelated publication must not invalidate unchanged index entries merely because their generation differs.

A creates/validates capability scope and stage transitions. Tokens expire or become invalid after lease/lifecycle changes. Allowed staged input is already privacy-sanitized; B cannot request raw content or unrestricted identity data. Staging and publication use compare-and-set; no SQL transaction spans model/index network calls.

```text
ArtifactRepository.load_staged_record(cap: JobCapability, ref: RecordVersionRef) -> StagedRecord
ArtifactRepository.published_context(cap: JobCapability) -> WorkReadContext
ArtifactRepository.load_rebuild_plan(cap: JobCapability, plan_id: Id) -> RebuildPlan
ArtifactRepository.load_staged_artifacts(cap: JobCapability,
                                        artifact_key: string) -> StagedArtifacts | null
ArtifactRepository.stage_artifacts(cap: JobCapability, artifact_key: string,
                                  batch: ArtifactBatch) -> StagedArtifacts
ArtifactRepository.release_overview(cap: JobCapability, input: OverviewCandidate) -> Overview

MaintenanceHandlers.process_record(cap: JobCapability, ref: RecordVersionRef) -> MaintenanceResult
MaintenanceHandlers.rebuild_affected(cap: JobCapability, plan: RebuildPlan) -> MaintenanceResult
MaintenanceHandlers.remove_index_entries(cap: JobCapability, entry_ids: Id[]) -> MaintenanceResult
MaintenanceHandlers.reconcile(cap: JobCapability) -> ReconciliationReport

JobCoordinator.claim(worker_id: Id, kinds: JobKind[]) -> JobLease | null
JobCoordinator.heartbeat(lease: JobLease) -> JobLease
JobCoordinator.advance(lease: JobLease, expected_stage: JobStage,
                       next_stage: JobStage, counts: map<string, integer>) -> JobLease
JobCoordinator.capability(lease: JobLease, stage: JobStage) -> JobCapability
JobCoordinator.publish(lease: JobLease, results: MaintenanceResult[]) -> Job
JobCoordinator.fail(lease: JobLease, code: string, retryable: boolean) -> Job
JobLease {job: Job, work: WorkPlan, lease_token: string, expires_at: Instant}
WorkPlan {
  document_ids: Id[], person_ids: Id[], record_versions: RecordVersionRef[],
  rebuild_plan_ids: Id[], removal_entry_ids: Id[]
}
ReconciliationReport {
  checked_entry_ids: Id[], missing_entry_ids: Id[], obsolete_entry_ids: Id[],
  unresolved_operation_ids: Id[], corrective_operation_ids: Id[]
}
```

`claim` returns null when no job is available. `load_staged_artifacts` returns null only when no checkpoint exists for the authorized job/key; stale or unauthorized checkpoints raise an error instead. The durable runner is A-owned and invokes B handlers registered by C. Its internal WorkPlan contains only IDs, never raw personal text; it is not the public Job DTO. A updates the inventory/plan during its own parsing and erasure stages. `advance` checks the expected current stage and allowed transition under the live lease, atomically persisting progress. It advances recorded stages, obtains stage-specific capabilities, and publishes only after validating every required result, dependency and completed index operation. Handlers cannot mark a job completed themselves. A lease heartbeat cannot revive a superseded lease.

Allowed normal stage sequences are below. The coordinator owns each transition; handlers cannot skip a required stage by returning success.

| Job kind | Normal stage sequence | Completion condition |
| --- | --- | --- |
| ingest | received -> parsed -> privacy_ready -> extracted -> indexed -> published | All required base records/artifacts coherently published |
| activate | received -> rebuilding -> indexed -> published | Rebuilt active version is eligible |
| deactivate | invalidating -> rebuilding -> verifying -> done | Source remains inactive; affected derived views invalidated/rebuilt |
| delete_document / erase_person | invalidating -> inventory -> draining -> sanitizing -> rebuilding -> removing_index -> verifying -> done | All controlled-store cleanup verified, no unresolved earlier writer |
| rebuild_aggregate | received -> extracted -> verifying -> published | Dependencies current; any public overview has passed grounding |
| reconcile | inventory -> removing_index -> verifying -> done | Required corrections verified and unknown outcomes resolved |

Deletion may have no replacement content to rebuild; still record a zero-work stage. Erasure may perform multiple tracked index removals/upserts within its rebuilding/removing_index phases. Optional re-embedding is driven by changed inputs, never by unrelated global revisions alone. Job state is pending before claim, running under a valid lease, completed only at its final verified stage, or failed at the last attempted stage with a safe code. Retry retains the job ID and resumes idempotent work with a new lease; it never restores old eligibility or releases a barrier before verification.

A base record batch publishes without waiting for topic/overview rebuilds. The publication transaction marks affected aggregates pending and creates rebuild jobs. Aggregate jobs use published contexts, stage dependency-bound summaries and release only grounding-reviewed overview claims. A changed dependency rejects aggregate publication. Proposed history is internal until consequential relations have passed B review.

### Durable staged-artifact recovery

A stores one checkpoint per `(job_id, artifact_key)`. The key is compact JSON of `["record", record_id, record_version]` for record work, or `["aggregate", rebuild_plan_id]` for aggregate work; IDs retain their original bytes. The key does not contain a lease token, timestamp or randomly generated batch ID. All producers use the shared key encoder.

B calls `load_staged_artifacts` before generating maintenance outputs. On a miss, B generates and validates the complete ArtifactBatch, then calls `stage_artifacts`. A atomically saves the batch and checkpoint mapping before returning. No index operation may be prepared or dispatched for that batch before staging succeeds. The batch includes the summaries, original timestamps/generator versions, chunk descriptors, dependencies and pinned embedding model/dimension/input hashes needed to continue.

On a hit, B reuses the saved batch verbatim: no regeneration of summaries, history, IDs, timestamps or embedding-input definitions. It reads the authorized staged source spans to reconstruct the exact saved chunk inputs, verifies their hashes, then resumes the durable index-operation ledger. Embeddings may be recomputed from those identical inputs using the saved model/dimension if no verified completed index write can be reused. A missing saved model/provider is a visible retryable dependency failure, not permission to change the checkpoint.

A validates capability scope, current lifecycle revision, source versions and dependencies on both checkpoint reads and writes. Ordinary lease renewal/retry may reload the same checkpoint under the replacement valid lease, retaining the original publication generation. An expired lease cannot read or save it. An erasure/source-version change makes the old checkpoint ineligible; it must not be returned as a cache miss and regenerated under the old job. A explicitly supersedes the obsolete work and schedules a new authorized job/plan when needed.

Staging is idempotent on job/key and batch content. Repeating identical content returns the existing StagedArtifacts; different content under that key or batch ID is `contract_violation`. A never silently overwrites a saved checkpoint. Content comparison includes timestamps and metadata, so retry must reuse the saved values.

After a crash:
- Before checkpoint commit: no index write was allowed; generation may restart.
- After checkpoint commit but before index dispatch: reload the batch and perform the missing index work without rerunning generation.
- After index dispatch or acknowledgement: reload the batch and inspect recorded operation outcomes. Reconcile pending/in-flight/unknown outcomes before another write; do not assume an unacknowledged write failed. Reuse verified completed operations, then let A publish.
- After publication but before the worker observes completion: A returns the already recorded publication/job result; no second record version or current index entry is created.

Checkpoint data is restricted preprocessing/derived storage, included in person/document erasure and dependency invalidation. Neither member reads nor agent tools can load it. A verifies all required artifacts before base-record publication and completes ingestion only when every required record is published.

Acceptance CT-17: persist an extraction checkpoint, stop the worker before indexing, restart and verify identical batch IDs/text/timestamps/hashes with no new maintenance-generation call. Repeat after index acknowledgement but before publication and verify one current version/entry set after recovery. Invalidate the lifecycle or source version and verify that the old checkpoint cannot be loaded or republished. A/B may develop checkpoint behavior using controlled outcomes and fixture ports. Acceptance executes the real worker with PostgreSQL, actual B processing and Qdrant; G1/G3 retain the persisted and provider-call evidence.

## 9. Durable external index operations

A owns the durable operation ledger; B owns actual Qdrant calls. This boundary is essential to independent testing of deletion and delayed writes.

```text
IndexOperationInput {
  idempotency_key: string, action: upsert | delete,
  entries: IndexEntry[], entry_ids: Id[]
}
IndexOperation {
  id: Id, job_id: Id, project_id: Id, action: upsert | delete,
  entry_ids: Id[], lifecycle_revision: Revision,
  state: pending | in_flight | succeeded | failed | unknown
}
OperationTicket {operation: IndexOperation, completion_token: string}
IndexOutcome {
  state: succeeded | failed | unknown, completed_entry_ids: Id[],
  error_code: string?, observed_at: Instant
}
IndexOperationLedger.prepare(cap: JobCapability, input: IndexOperationInput) -> OperationTicket
IndexOperationLedger.start(cap: JobCapability, operation_id: Id) -> None
IndexOperationLedger.report(ticket: OperationTicket, outcome: IndexOutcome) -> None
IndexOperationLedger.list_operations(cap: JobCapability, page: PageRequest) -> Page<IndexOperation>
IndexOperationLedger.get_entries(cap: JobCapability, entry_ids: Id[]) -> IndexEntry[]
```

For upsert, `entries` is nonempty and `entry_ids` equals their IDs. For delete, `entries=[]` and IDs must be in the job's removal inventory. All operations are restricted to the project's configured collection namespace; B cannot select an arbitrary collection from public input.

Prepare durably records intent and validates hashes/versions before B calls Qdrant. Start records dispatch and rechecks the capability. Even if the lease expires immediately after start, the operation stays outstanding until its outcome is known. B waits for Qdrant acknowledgement and verifies expected IDs/version/hash (or absence for deletion); a timeout becomes `unknown`, never assumed failed/no-write.

A completion token authorizes only reporting an outcome for that exact recorded operation. It can report a late result after the job lease is stale; it cannot stage, publish, renew a lease or create a new operation. Duplicate identical reports are idempotent; incompatible reports require reconciliation. A must retain late reports so an obsolete successful upsert can be removed.

An erasure barrier invalidates old publication tokens, inventories pending/in-flight/unknown operations and waits for writers to drain or be proven stopped. Reconciliation confirms final remote state and removes obsolete outputs. Merely observing an absent point while an old writer can still finish does not settle an unknown upsert. Cleanup is not complete until no pre-barrier writer can recreate it and every required removal is verified. A never drops this requirement because B times out.

Erasure inventory covers retained uploads, raw/intermediate/current/old versions, filenames/headers, identities, summaries/history, pending work, messages/titles, quotes/caches and content-bearing logs in controlled storage. Replace attribution with `[deleted user]`, preserve decisions, rebuild changed embedding inputs and remove obsolete vectors/payloads. Audit stores IDs/counts/outcomes, never erased names. Original corpus inputs outside application storage, backups and external provider retention remain explicitly inventoried limits; this interface makes no full GDPR-compliance claim.

## 10. Optional preprocessing detector boundary

```text
PrivacyDetectionInput {project_id: Id, record_id: Id, text: string}
Detection {
  start: integer, end: integer,
  kind: name | email | phone | postal_address | private_discussion,
  identity_hint: string?, confidence: certain | uncertain
}
PrivacyDetectionResult {detections: Detection[], unresolved: boolean}
PrivacyDetector.detect(input: PrivacyDetectionInput) -> PrivacyDetectionResult
```

This is the only optional cross-slice provider interface that may receive restricted unnormalized input, under separately configured authorization. Offsets use Unicode code points. A validates ranges, resolves identity/alias ambiguity, preserves supported operational facts and decides quarantine; detector confidence cannot override those checks. No detector result goes directly to B's memory/embedding pipeline. Rules-only/deterministic substitutes implement the same interface for S-A.

## 11. Required boundary examples and checks

[contract-examples.json](contract-examples.json) contains synthetic public response examples shared with C's fixtures. They are data examples, not evidence of a live result. G0 must encode the DTOs/protocols above. Checking examples against exported schemas is a development aid, not a substitute for running the product.

| Case | Producer obligation | Consumer assertion |
| --- | --- | --- |
| CT-01 session revoked after begin_chat | A rejects release | C returns 401 with no candidate claims |
| CT-02 wrong project/owner | A returns not_found before data | B/C never expose IDs, snippets or counts |
| CT-03 paginated record | A returns ordered spans/chunk IDs and bound cursor | B tracks actually supplied chunks; C follows cursor |
| CT-04 stale Qdrant hit | A omits canonical text for rejected entry | B never returns Qdrant payload as source text |
| CT-05 quote/digest mismatch | A rejects candidate | C returns safe failure, no unchecked answer |
| CT-06 matching chat retry | A replays one currently valid saved answer | C reuses request ID; no duplicate turn |
| CT-07 different input under same key | A returns idempotency_conflict | C does not silently overwrite/retry |
| CT-08 changed receipt | A returns 410, no old/new quote substitution | C clears popover and offers regeneration |
| CT-09 unknown upsert outcome | A retains outstanding operation | B reports unknown; cleanup UI stays incomplete |
| CT-10 late obsolete upsert | Ledger accepts outcome only, no publication | B removes point; A verifies before completion |
| CT-11 overview pending | A returns empty claims/receipts | C renders status, no raw memory prose |
| CT-12 model/reviewer unavailable | B raises provider_unavailable | C renders retryable failure |
| CT-13 malformed artifact/span | A rejects staging/publication | B records failure, no silent partial success |
| CT-14 fixture composition | C starts real routes with only contracts and fixture ports | Browser flows need no A/B runtime imports |
| CT-15 same-name people | A keeps distinct identity IDs | B filters IDs; C's erase confirmation targets one ID |
| CT-16 erasure barrier | A blocks upload/association/chat publication | C keeps unsent input only in memory and shows retry |
| CT-17 staged restart | A durably saves/reloads the exact authorized batch | B resumes index work without regenerating checkpointed model outputs; obsolete checkpoints are rejected |

Protocol conformance cases run against real producers and consumer substitutes using adapter factories. Source/record/model quality is tested in the owning slice; the whole pipeline is still verified through G1-G4. Any unresolved signature/type/state decision blocks G0 readiness and must be added here rather than invented independently.


## 12. Source compliance and unresolved document differences

This contract implements the existing delivery slice; it does not silently resolve disagreements among source documents. The hierarchy in the implementation README governs: production behavior defines observable requirements, the AI architecture supplies the selected technical direction, and delivery specs choose explicit provisional defaults. The DBML remains a candidate sketch; pseudonymization notes remain background.

| Source requirement | Contract location | Preserved behavior |
| --- | --- | --- |
| [Production sections 3.1, 4.1](../production-behavior.md) | sections 2–6; HTTP authentication and source routes | Project isolation, exact receipts, no inaccessible evidence |
| [Production sections 4.2–4.3](../production-behavior.md) | sections 3, 6–7 | Suggestions stay suggestions; supported conditions/attribution; source/effective/learned time; uncertainty |
| [Production sections 4.4](../production-behavior.md) | sections 5, 8–9 | Names/contact erasure throughout controlled stores; decisions retained; failure is not completion |
| [Architecture sections 3–5](../ai-agent-architecture.md) | sections 6, 8 | Privacy before downstream models; L1/L2 discovery, L3 evidence; ordered sibling-chunk expansion |
| [Architecture sections 6–8](../ai-agent-architecture.md) and [B3–B4](worker-b-intelligence.md) | sections 5–7 | Server context, independent reviewer, bounded repair, no factual draft streaming |
| [Architecture sections 9–11](../ai-agent-architecture.md) and [A3–A4](worker-a-evidence-platform.md) | sections 5, 8–9 | Exact versions, current eligibility, resumable erasure, fenced writes and final atomic release |
| [User features](../user-features.md) and [UI sections 1–4, 10](../user_ui.md) | sections 3, 5; HTTP browser behavior | Document list, source title/quote/new tab, admin controls, project selector and clear states |
| [C1–C4](worker-c-product.md) | HTTP specification and section 1 | Real routes with injected services, actual browser tests, CSRF, no-store, retry and unavailable states |
| [Independent testing](independent-testing.md) | sections 1, 11 | Separate substitutes/resources and later real integration |

Known differences remain explicit:

- `user_ui.md` specifies system-wide Administrator access, custom project roles and broader user/organization administration. Production behavior leaves system admin open, and delivery defaults select only project admin/member with no global bypass. The interfaces here implement that provisional delivery choice; they do not claim to satisfy the broader UI role matrix.
- `user_ui.md` permits a Basic User to use chat without project rights. The app can display chat and an empty project selector, but this delivery plan only defines project-grounded chat endpoints. A general non-project chat service remains unspecified; do not grant implicit project access or claim this broader behavior complete.
- Client/employee associations and project-local erasure are covered. Organization-wide deletion, global account/user discovery, project creation UI, custom role editing and cross-project association management are not silently added. Where the broad UI document expects these, they remain product-scope differences requiring reconciliation.
- Members seeing only active sources, admins seeing sanitized inactive previews, opaque personnel labels, project-local admin erasure, UTF-8 initial formats and ingestion-time removal of private discussion are the delivery plan's existing provisional defaults. They are not recast as previously approved production requirements.
- Actual project visualization content remains deferred. Status/overview endpoints support navigation and status only; they do not complete the visualization requirement.
- Integer pagination defaults, enum spellings, normalization, digest encoding, cookie/header names and port decomposition are interface decisions in revision 4. They preserve the behavior above; they do not establish model choice, new legal guarantees or a new deployment requirement.

Do not label this contract fully compliant with every historical document while these source differences remain unresolved. Required production evidence/access/chronology/erasure invariants are preserved; broader product scope still needs an explicit decision.
