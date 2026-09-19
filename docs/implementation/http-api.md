# HTTP API and browser contract

Contract revision 6 — 2026-09-19. Revision 6 adds the public project timeline shape to revision 5's checkpoint contract. Read [shared-interfaces.md](shared-interfaces.md) for DTO fields, domain rules and service ownership. This document is a specification, not a claim that routes already exist. C implements these actual routes against injected service interfaces.

The API in this document is the application's browser-facing API. PostgreSQL may run locally and A connects directly using the native database protocol; that does not remove these routes or expose database credentials to the browser. A/B service calls inside the backend remain in-process interfaces.

## Verification policy: real services

Verification follows [real-service-verification.md](real-service-verification.md). Run the actual implementation against real PostgreSQL, Qdrant, configured model/reviewer/embedding services, FastAPI and a browser wherever the required operation uses them. Synthetic input documents are encouraged; fake service responses are not acceptance evidence.

Contract tests, schema examples and fixture-service scenarios below are development aids. They may establish implementation readiness but cannot mark product behavior verified. Cross-slice live checks stay pending until real adapters are available. Independent code handoff remains allowed, explicitly labeled implementation-ready rather than live-verified; missing services are reported as blockers, never replaced by a mock pass.


## 1. Common transport rules

All paths use the same origin as the frontend. JSON bodies/responses use UTF-8. `p` is the selected project ID. Authentication uses an opaque `relex_session` cookie with `HttpOnly; SameSite=Lax; Path=/` and `Secure` in HTTPS deployments. An explicit loopback HTTP development setting may omit Secure; production must not silently downgrade it. Never serialize session tokens or credentials into response JSON, browser storage, traces or static assets.

Login requires JSON and an Origin matching the configured trusted frontend origin. Missing/untrusted Origin on login is rejected. A successful login rotates the session token and returns `Me`, including a session-bound CSRF token. Subsequent POST/DELETE requests require a trusted Origin and `X-CSRF-Token` validated through A. `GET /api/me` restores the in-memory CSRF token after reload. This includes search POSTs even though they are logically read-only. GET routes have no side effects.

C authenticates, obtains server-created project context, enforces CSRF/transport validation, calls the relevant service and serializes an explicit public response model. A rechecks business authorization; B never receives a caller-constructed context. A project nonmember or wrong conversation owner receives 404, while an authenticated member lacking admin receives 403.

Sensitive API/source responses and errors use `Cache-Control: no-store`. Source page HTML contains only the application shell; the source API independently authenticates. Clear project state on project switch/logout and discard late responses belonging to an earlier session/project. No private source/chat storage in localStorage or service-worker caches.

List endpoints accept `cursor` and `limit` (default 25, maximum 100) and return `Page<T>`. Cursor reuse requires unchanged arguments. `null` terminates pagination. Unknown fields and unsupported query parameters return 422. Lists do not include inaccessible totals.

Required input limits for the initial interface: question/search text 1–8,000 Unicode code points; conversation title 1–120; filename 1–255; person display name 1–255; contact value 1–500. Names/titles are normalized through A before storage/display. Upload bytes use a single configured `upload_limit_bytes` enforced by C and A; publish its value in deployment instructions. Limit errors must not echo submitted personal text. Page/token/deadline configuration is shared with fixtures, not independently guessed by each person.

These limits, cookie/header names and route decomposition are revision 4 interface defaults; they do not change source-document access or evidence requirements.

## 2. Session and project routes

| Method and path | Input | Success | Service calls |
| --- | --- | --- | --- |
| POST `/api/login` | JSON `{email,password}` | 200 `Me` plus session cookie | `auth.login` |
| POST `/api/logout` | No body; CSRF | 204; clear cookie | `auth.logout` |
| GET `/api/me` | Session cookie | 200 `Me` | `auth.authenticate`, `auth.me` |
| GET `/api/projects` | Page query | 200 `Page<Project>` | `projects.list_projects` |

All project routes below first call `auth.authenticate` then `projects.authorize`. State-changing routes also validate CSRF. On logout, always clear local browser state; an already expired session may return 401 and must still clear the stale cookie/client state. A revokes valid sessions so in-flight answer release also fails.

An authenticated user with no memberships receives an empty project list and can enter the app. No project access is inferred from client/employee associations. Non-project general chat is outside the currently specified service scope; see the source differences in the shared contract.

## 3. Documents, sources and search

| Method and path | Input | Success | Service / access |
| --- | --- | --- | --- |
| GET `/api/projects/{p}/documents` | Page query | 200 `Page<Document>` | `documents.list_documents`; member/admin |
| GET `/api/projects/{p}/documents/{id}/records` | Page query | 200 `Page<RecordSummary>` | `documents.list_records`; current eligible records |
| POST `/api/projects/{p}/documents` | Multipart `file` and `record_type` | 202 `Job` | `documents.submit_upload`; admin |
| POST `/api/projects/{p}/documents/{id}/activate` | No body | 202 `Job` | `documents.mutate_document(...,activate)`; admin |
| POST `/api/projects/{p}/documents/{id}/deactivate` | No body | 202 `Job` | `documents.mutate_document(...,deactivate)`; admin |
| DELETE `/api/projects/{p}/documents/{id}` | No body | 202 `Job` | `documents.mutate_document(...,delete)`; admin |
| GET `/api/projects/{p}/records/{id}` | Page query | 200 `RecordPage` | `sources.read_record`; active answer evidence |
| GET `/api/projects/{p}/sources/{id}` | Required `version` and `span`; optional `cursor,limit` | 200 `SourcePage` | `sources.read_source`; server-derived preview purpose |
| GET `/projects/{p}/sources/{id}` | Required `version` and `span` | 200 app shell; source content only after authorized API fetch | C source page |
| POST `/api/projects/{p}/search` | JSON `{query,filters,cursor?,limit?}` | 200 `SearchPage` | `intelligence.search_memory`; member/admin |
| GET `/api/projects/{p}/filters` | No input | 200 `FilterOptions` | `sources.get_filters` |

`record_type` values are `email, transcript, report, specification`. Initial content support is UTF-8 text only; an enum does not imply PDF/OCR support. Unsupported content yields 422; too-large upload yields 413. C passes bounded file bytes to A and does not retain a second unmanaged upload copy.

Search filters are optional fields inside `filters`: `date_from, date_to, record_type, original_doc_id, topic_id, person_id`. Use `filters:{}` for no filters. Date ranges are inclusive and `date_from <= date_to`; unknown source dates do not match bounds. Search state, including all filters, remains fixed when continuing a cursor.

A source URL requests an exact version/span. A changed version returns 410, not a new quote supporting an old claim. Do not fetch all earlier pages to reach a citation: the first source request is centered on `span`. The source shell handles 401/404/410 visibly without embedding protected source text into HTML. An admin's inactive source preview never makes it answer evidence.

`Document.records_url` is the relative records endpoint above. `Receipt.source_url` is the relative browser source path with version/span. A validates that receipt URL fields agree with `evidence_ref`. For multiple contiguous receipt spans, the URL centers the first and the API supplies surrounding context; highlight all available receipt spans when navigating from the receipt.

## 4. Conversations and answers

| Method and path | Input | Success | Service |
| --- | --- | --- | --- |
| POST `/api/projects/{p}/conversations` | JSON `{}` or `{title}` | 201 `Conversation` | `conversations.create` |
| GET `/api/projects/{p}/conversations` | Page query | 200 `Page<Conversation>` | `conversations.list` |
| GET `/api/projects/{p}/conversations/{id}/messages` | Page query | 200 `Page<Message>` | `conversations.messages` |
| POST `/api/projects/{p}/chat` | JSON `{question,conversation_id,request_id}` | 200 `Answer` | Sequence below |
| GET `/api/projects/{p}/answers/{id}` | No input | 200 `Answer` | `conversations.get_answer` |
| GET `/api/projects/{p}/answers/{id}/receipts/{receipt_id}` | No input | 200 `Receipt` | `conversations.get_receipt` |

Only the conversation owner can read messages/answers/receipts, including when another caller is a project admin. Create-conversation title defaults to `New Chat`; do not put an unchecked question/name into the title.

The actual chat route performs this sequence:

1. Authenticate, validate CSRF and authorize the selected project.
2. Validate `ChatInput` and call `conversations.begin_chat(ctx,input)`.
3. If A returns `replay`, return that reauthorized saved answer; do not rerun B.
4. If A returns `ready`, call `intelligence.answer(ctx,begin.input)`. Never supply client history or the original unnormalized question separately.
5. Pass the internal candidate to `conversations.release_answer(ctx,begin.attempt,candidate)`.
6. Serialize only the returned public `Answer`. On failure, report the original safe error and call `fail_chat` for the attempt when appropriate; do not serialize the candidate.

This sequence executes unchanged with fixture or real services. Transport deadlines cannot relax release deadlines. Cancellation never authorizes an unchecked response or stale persistence.

The browser generates one stable request ID per submitted question and reuses it for transport retries. Same key while running yields `409 request_in_progress`; same key with different input yields `409 idempotency_conflict`. A successful replay is 200 with the same answer ID. An invalidated saved answer yields 410: regeneration uses a new request ID. A retry after a transient failed attempt may reuse the original ID/input, subject to A's lease and snapshot rules.

No factual draft streaming. UI processing indicators may be local; the final HTTP answer arrives only after review and atomic release. `Answer.cannot_establish` is an answer outcome, not necessarily an HTTP error. Provider failure is 503 and must not be styled as a verified answer.

Re-fetch the owner-scoped receipt when opening its popover by hover, focus or tap. Show the safe source title and quote, with a source link opening a new tab using `noopener`. A failed/410 receipt fetch removes cached quote content. Previously delivered pixels cannot be revoked; all subsequent fetches still enforce current eligibility.

## 5. Status, administration and jobs

| Method and path | Input | Success | Service / access |
| --- | --- | --- | --- |
| GET `/api/projects/{p}/status` | No input | 200 `ProjectStatus` | `sources.get_status`; member/admin |
| GET `/api/projects/{p}/overview` | No input | 200 `Overview` | `sources.get_overview`; member/admin |
| GET `/api/projects/{p}/timeline` | Page query | 200 `Page<TimelineRecord>` | `sources.get_timeline`; member/admin; active records only |
| GET `/api/projects/{p}/members` | Page query | 200 `Page<Member>` | `administration.list_members`; admin |
| POST `/api/projects/{p}/members` | JSON `{user_id,role}` | 200 `Member` | `administration.set_member`; admin |
| DELETE `/api/projects/{p}/members/{user_id}` | No body | 204 | `administration.remove_member`; admin |
| GET `/api/projects/{p}/people` | Page query | 200 `Page<Person>` | `administration.list_people`; admin |
| POST `/api/projects/{p}/people` | JSON `PersonInput` | 200 `Person` | `administration.associate_person`; admin |
| POST `/api/projects/{p}/people/{id}/erase` | No body | 202 `Job` | `administration.erase_person`; admin |
| GET `/api/projects/{p}/jobs` | Page query | 200 `Page<Job>` | `administration.list_jobs`; admin |
| GET `/api/projects/{p}/jobs/{id}` | No input | 200 `Job` | `administration.get_job`; admin |
| POST `/api/projects/{p}/jobs/{id}/retry` | No body | 200 `Job` | `administration.retry_job`; admin |

Membership removal revokes access; person erasure removes names/contact details from project evidence while preserving decisions. These are distinct actions and confirmations. The last admin cannot be removed without a supported transfer.

Deleting a document or erasing a person requires a browser confirmation naming the exact sanitized target/project. The server still authorizes the ID; a UI confirmation flag is not permission. Public routes cannot set a job state or declare cleanup completed.

The browser discovers jobs again after reload through the paginated admin job list. Pending/running/failed are distinct from completed. Show safe error codes and retry only when `retryable=true`. While `write_barrier=true`, show why uploads/identity/chat writes are temporarily unavailable; preserve unsent question text only in memory.

`Overview.state=ready` exposes only reviewed claims/receipts; pending/failed/unavailable exposes empty arrays. The separate timeline exposes explicitly labeled L1/L2 discovery summaries for current active records, never as reviewed claims, and links each record to processed canonical content at a summary dependency span. Project status is eligible counts plus explicitly labeled operational status. Broader aggregate visualization content remains deferred.

## 6. Browser fixture scenarios

C's test composition injects fixture services into the real `create_app`. Scenario controls live in test code/fixtures, not public production routes. Session tokens and cookies are synthetic but still exercise C's real request parsing, cookie setting, CSRF middleware/dependencies, error mapping and response serialization.

| Fixture scenario | Controlled A/B outcome | Browser/API expectation |
| --- | --- | --- |
| admin-upload-success | Upload job advances to published | Progress -> document list -> source |
| member-no-admin | authorize(admin) raises forbidden | No admin controls; direct mutation returns 403 |
| outsider-project | authorize returns not_found | No titles/counts/snippets |
| long-record | Source pages around cited span | Correct highlight and ordered navigation |
| answer-success | B returns candidate; A releases Answer | Claims and receipt interactions render |
| release-changed | A rejects after B succeeds | 409 UI; no candidate claims in response |
| reviewer-down | B raises provider_unavailable | Retryable failure, no verified answer |
| stale-receipt | Saved receipt now unavailable | Cached quote removed; regeneration offered |
| chat-double-submit | begin_chat returns in-progress/replay | One persisted turn and stable answer ID |
| logout-during-chat | A refuses late release | Late response discarded; no stale claim display |
| erasure-failure-retry | failed job, then resumed job | Correct target, failure and final completion state |
| project-switch | Delayed response from previous project | Response discarded and project state cleared |
| overview-pending | Empty claims with pending state | No overview summary; the independently authorized record timeline may remain visible |
| record-timeline | Four active records with distinct types, source times and L1/L2 summaries | Chronological horizontal cards, type colors, dependency-backed source links, scrolling and time-scale zoom |
| no-memberships | Empty project list | App accessible; no project-derived data |

Fixtures assist C's development only and do not verify product behavior. Real auth/SQL, live model/index services and the actual combined browser flows are required for acceptance.

## 7. Generated client and contract checks

C exports OpenAPI from these actual routes and shared DTOs using fixture composition, without production services. Generate frontend types/client from that export; do not hand-maintain competing evidence shapes. G0 fixes the generator command and checks generation drift.

Validate [contract-examples.json](contract-examples.json) against response schemas, then run shared CT-01 through CT-18 plus the scenarios above. Tests must assert forbidden fields are absent: session/lease tokens, identity mappings, raw input, review reasoning, internal operation tickets and unreviewed candidates. Fixtures may expose only the same public DTOs as production routes.
