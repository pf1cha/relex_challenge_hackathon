# Three-slice implementation delivery spec

Status: frozen
Revision: 4
Service contract: revision 5
Baseline: 2063eba9b3f9619653a5b1640b2e87ce725b1c4d
Repository: `verda:/mnt/relex-kai` (connect with `ssh verda`)
Objective: Deliver the documented project-scoped evidence, reviewed-answer and browser product through three parallel implementation workers, with independently runnable slice verification and real integrated acceptance.

## Revision history

- Revision 4: Explicitly confirmed by the user on 2026-09-19 with “start the parallel implementation”. Frozen for A/B/C dispatch.

- Revision 1: Initial dispatch draft; self-review identified restart-contract, handoff-gating and inherited-state issues.
- Revision 2: Fixed all three findings at the user's request. Added revision 5 checkpoint recovery/CT-17, separated standalone isolation from shared concurrency acceptance, corrected .env.example baseline status and refreshed input hashes. Superseded by revision 3 before dispatch.

- Revision 3: At the user's request, verification requires running real services and the actual product. Contract tests and fixture services are development aids only; handoff may be implementation-ready with live verification pending. Added the real-service runbook and refreshed hashes. Superseded by revision 4 before dispatch.

- Revision 4: Bounded re-review clarified development versus live runners, real-service concurrency evidence, G0 readiness, composition/bootstrap ownership and live negative-path coverage. No product scope or service DTO change. Awaiting explicit confirmation of revision 4; no workers dispatched.

## Authoritative inputs and scope decision

Read this entire file and all ten pinned implementation documents below before editing. They supply the detailed requirements; this file fixes dispatch, acceptance, ownership and stopping rules. The parent owns this spec. Workers/reviewer may not change it or its referenced specification documents.

Confirmation adopts the current delivery scope for this run: project-scoped admin/member, project-grounded chat, project-local erasure, local PostgreSQL via a native driver, and the existing provisional privacy/rendering defaults. It does not resolve the broader UI specification in favor of global admins, custom roles, non-project chat or organization-wide management. Those remain excluded as documented in shared-interfaces.md, source-compliance section. Actual visualization content remains deferred.

The acceptance contract comprises `shared-interfaces.md` (including CT-01 through CT-17), `http-api.md`, `contract-examples.json`, `independent-testing.md`, `real-service-verification.md`, architecture and A1-A4/B1-B4/C1-C4 worker specs. Production behavior requirements remain authoritative for evidence, chronology, access and erasure. For dispatch, handoff status and verification only, this revision and real-service-verification.md take precedence over earlier development/fixture wording in the referenced plans; that precedence does not waive any product behavior. If those inputs make a required behavior impossible or contradictory, stop the affected work and report the contradiction; do not invent a new semantic contract.

## Required outcomes and acceptance evidence

| ID | Owner | Required outcome | Acceptance evidence |
| --- | --- | --- | --- |
| R-G0 | A and C; B prepares owned prompts/fixtures | Importable revision 5 DTOs/protocols/errors, inert imports and independent setup | Run actual imports/startup of the shared starter without unrelated services; schema/example checks are optional development checks, not product verification |
| R-A1 | A | A1 authenticated sessions, project boundaries, canonical repositories and migrations | Real PostgreSQL: admin/member/outsider, project/owner denial, logout, repeated migration/restart; relevant CT cases |
| R-A2 | A | A2 supported ingestion, provenance, privacy processing, staged versions and coherent publication | Synthetic bundled emails/transcripts/reports; real persisted records/spans/jobs, quarantine, CT-17 checkpoint reload and interrupted publication/retry |
| R-A3 | A | A3 eligibility, conversation ownership/idempotency, exact receipts and atomic release | Run A/database probes for logout/revocation/source-change races, request replay and stale receipts using candidates captured from real B review; deliberate malformed inputs test rejection, never stand in for a successful reviewer |
| R-A4 | A | A4 resumable erasure preserving decisions; write barriers and fenced jobs/index operations | Run A with real PostgreSQL for owned lifecycle behavior; verify actual erasure/index outcomes with real B/Qdrant under R-G3. Controlled callbacks are development evidence only |
| R-B1 | B | B1 sanitized L1/L2 maintenance, chunking, real embedding/indexing and aggregate dependencies | Run real generation/embedding/Qdrant calls; verify persisted canonical outputs with real A repositories for acceptance, including changed/unchanged hashes, CT-17 recovery and reviewed overview |
| R-B2 | B | B2 common hybrid search, filters, canonical validation and complete selected-record expansion | Run real PostgreSQL lexical retrieval and Qdrant semantic retrieval over synthetic source data; observe late qualification, pagination/budget and stale-candidate rejection |
| R-B3 | B | B3 decision chronology, bounded answer workflow and B-C1 through B-C9 | Real generation against fixed synthetic fixture dates/scopes; receipts and prohibited-claim assertions for every case |
| R-B4 | B | B4 independent review, bounded repair and index lifecycle handlers | Real reviewer finds unsupported attribution/counterevidence; provider failure, exact digest/quotes, real index replacement/removal and reconciliation |
| R-C1 | C | C1 actual app routes, generated client, session UI, setup and bootstrap composition | Run FastAPI/browser with real session/database services; login/logout, role/project navigation, CSRF and direct URL errors; build/typecheck is supplemental |
| R-C2 | C | C2 upload, searchable documents, filters and source/citation viewer | Actual browser through real routes and real A/B adapters: upload/progress/failure, hover/focus/tap, new tab, centered/paginated source and stale receipt |
| R-C3 | C | C3 reviewed chat orchestration, owner-scoped history and project status/overview | Actual route/browser proves begin -> B -> atomic release before claims; withheld/error/partial/replay states; no unchecked overview prose |
| R-C4 | C | C4 admin membership/person/document lifecycle and job recovery UI | Actual browser confirmations, denied admin calls, failed/retry/completed states, reload discovery, barrier and project/session state clearing |
| R-S | Each worker | Independent development/code handoff plus isolated live runner | Development runner needs only G0 and the owned slice. Live runner executes real required dependencies and two distinct run IDs; missing real adapters leave verification pending without blocking implementation-ready handoff |
| R-G1 | C coordinates; A/B supply real adapters | Real upload -> privacy/memory/index -> publication -> authorized source | Actual authenticated browser, PostgreSQL and Qdrant; outsider denied |
| R-G2 | C coordinates; A/B supply real adapters | Real retrieval -> independent review -> atomic release -> receipt/source | Actual browser question, source quotes and saved-answer eligibility; no mocks passing this gate |
| R-G3 | C coordinates; A/B supply real adapters | Real deactivation/reactivation/deletion/person erasure across controlled stores | Failure/retry, late upsert and in-flight invalidation; real SQL/index inspection and preserved decisions |
| R-G4 | C coordinates; independent reviewer verifies | Real assembled product, restart and shared concurrency acceptance | All worker cases accounted for, persistence/recovery, source/version/access boundaries, simultaneous A/B/C runner isolation and explicit visualization/retention limits |

The source worker specs contain the scenarios for each row; `real-service-verification.md` defines acceptable execution evidence. Use three explicit states: implementation-ready, live-verified, and live-verification-blocked. A worker may hand off implementation-ready code without waiting for another slice, listing all pending real-service checks. Fixture/contract checks cannot mark a behavioral requirement live-verified. The shared A/B/C concurrency check belongs to R-G4 and cannot block independent code handoff. Product completion requires all required rows verified on real services plus independent reviewer PASS.

## Parallel dispatch and G0 preparation

Dispatch exactly three implementation workers: A, B and C, with their exact worker-spec path and this file's absolute remote path. No descendants.

The shared starter does not exist at this baseline. Initial work is bounded preparation: A owns contract types/conformance definitions; C owns minimal packaging, composition and fixture app setup; B owns provider schemas/prompts and synthetic fixture preparation without inventing incompatible contracts. A/C announce G0 readiness through coordinator messages. G0 checks importable types/ports and actual owned entry-point imports; writing/collecting contract tests is optional development support, not a mandatory acceptance gate. Once G0 is ready, all three continue independently in their own paths, using substitutes where other slices are unfinished. Do not wait for another slice's runtime implementation.

This is the necessary shared-setup exception to fully independent work; it is not an A1-before-B/C delivery gate. The parent coordinates boundaries and later review, but does not implement competing versions or run the full test suite.

Workers read repository cwd/status/HEAD and this spec's status/revision before edits. They must report those values and map progress/evidence to IDs above. Use only the authoritative remote checkout. Preserve all pre-existing changes, including staged content; do not reset, stash, clean or overwrite them.

## Allowed write scope

Use the exclusive path table in the implementation README:

- A: `backend/app/evidence/`, `backend/app/contracts/`, `backend/migrations/`, `backend/tests/evidence/`, `backend/tests/contracts/`, `scripts/evidence/` and `docs/implementation/evidence-a.md`.
- B: `backend/app/intelligence/`, `backend/tests/intelligence/`, `scripts/intelligence/` and `docs/implementation/evidence-b.md`.
- C: `backend/app/api/`, composition/config/entry-point files listed in README, `backend/tests/product/`, `frontend/`, `scripts/product/`, `fixtures/implementation/`, dependency manifests, `.env.example`, root `README.md` and `docs/implementation/evidence-c.md`.

At the pinned baseline, `.env.example` is committed and clean. C may extend it while preserving existing entries and any subsequent user edits; never copy private secrets into it. Do not modify private `.env`, source corpus, source behavior docs, spec files or another worker's implementation. Request coordinated changes through the parent rather than editing another owner's files.

Commit owned implementation progressively, with commits serialized through the coordinator because this checkout/index is shared. Stage/commit explicit owned files only; never use `git add .`, `git commit -a` or include inherited changes in an implementation commit. If a file already has staged changes, retain that inherited state and agree the commit boundary with the parent first. The coordinator may defer commits until a safe boundary rather than disturb the user's index. No push, PR publication or deployment is authorized.

## Invariants and direct regression surfaces

- I-ACCESS: No project/owner bypass through source URLs, snippets, summaries, conversations, fixtures or model tools.
- I-EVIDENCE: Every released factual claim has eligible exact-source support and the required review binding; unreviewed drafts are never streamed or exposed.
- I-PRIVACY: Names/contact removal preserves decisions and uses `[deleted user]`; all controlled copies and delayed writers remain in scope; no false completion or full-GDPR claim.
- I-CHRONOLOGY: Proposal, commitment, superseded decision and never-true correction remain distinct; neither upload order nor confidence invents authority.
- I-BOUNDARY: PostgreSQL is authoritative via A's native driver; Qdrant is a candidate index; B/C use injected ports; fixtures are test-only.
- I-PRESERVE: Existing user/source/configuration changes and other workers' data/processes are preserved. Changes in allowed paths must not break existing documented behavior outside this implementation.
- I-CONTRACT: Frozen DTO/HTTP semantics and dependency direction stay compatible. Any required semantic change needs a new spec revision and human confirmation.

Only defects introduced by the implementation diff that violate these invariants or a required row are blocking direct regressions. Pre-existing unrelated defects, speculative hardening and broad architecture audits are out of scope.

## Non-goals and authority limits

No system-wide admin bypass, custom-role designer, general non-project chat, organization-wide erasure, PDF/OCR pipeline, actual visualization design, SSO, graph database or hosted database HTTP gateway.

Running local development services, creating isolated synthetic test databases/collections, installing project-scoped dependencies and using already configured/authorized providers with synthetic data are implementation activities. Inspect actual available runtime/services before changing them. Use existing authorized resources or user-owned processes; report missing privileges/prerequisites rather than altering host-wide services or another user's database. Do not send the private corpus to a new endpoint, purchase resources, change firewall/system configuration, publish externally or destroy existing application data.

External retention/backups and downloaded browser content remain explicit limitations. Local PostgreSQL means the backend host (`verda` initially), not a browser-to-database connection.

## Verification tiers and review

1. G0 import/startup checks establish that implementation can proceed. Contract/schema tests may help development but do not verify the product.
2. Workers execute actual owned service code and its real dependencies. A uses PostgreSQL; B uses generation/reviewer/embedding endpoints and Qdrant; C uses FastAPI and a real browser. For an operation spanning slices, acceptance additionally requires those slices' real adapters and PostgreSQL repositories.
3. Execute the flows in `real-service-verification.md` using synthetic input records, not synthetic service responses. Capture commands, exit status, service/model versions, ports/process IDs, API/browser observations and persisted SQL/Qdrant state. A successful health check alone is insufficient.
4. Missing adapters, services, provider credentials or browser access are specific blockers. Continue independent implementation where possible; label the affected live checks pending/blocked. Do not substitute mocks, contract-test passes or static inspection for those checks.
5. One independent reviewer reads the frozen inputs, reviews the diff from baseline and performs focused real-service probes. The reviewer need not repeat every worker workflow, but PASS requires real execution evidence for every required row and independent probes of critical changed paths.
6. Inject failures into the running stack using owned process restart, controlled dependency interruption, constrained budgets or a test-only pause around the real index adapter. The success/cleanup path must still execute real services and persistence. Never use a canned success response to prove completion.
7. Run no broad test suite as a substitute for product execution. Broader live replay is justified only by a shared behavior change, a failure exposing another affected path, or a concrete regression. Parent does not run full suites.

The reviewer returns PASS or a finite prioritized finding list; each blocker maps to a required ID or invariant/direct regression. Scope stays bounded to the changed product. No unrelated cleanup is required for acceptance.

## Completion and stopping rules

Do not start implementation until this exact revision is explicitly confirmed and status is changed to frozen with confirmation recorded. The request for three workers sets worker count; it does not bypass the skill's saved-revision confirmation gate.

After dispatch, do not poll or interrupt active workers. Wait for their own messages/completion; do not duplicate implementation while waiting. When a slice is complete, preserve its agent for focused follow-up and integration support.

Repair confirmed findings proportionally using the original owner for small fixes; substantial fixes may use a replacement worker after the relevant slot is free. Re-review only accepted findings, touched requirements and concrete repair regressions. New semantics require a revised spec and renewed confirmation. Repeated scope drift triggers a convergence audit, not an unlimited expansion of requirements.

Declare complete only with every required row evidenced, relevant direct regressions resolved and bounded reviewer PASS. Otherwise report exact unfinished/blocked requirements and verification limits.

## Pinned input and inherited-state snapshot

The baseline commit had a clean tracked worktree. The hash table pins the current saved source/implementation contracts, including the coordinator's later uncommitted document revisions. The status block records that original baseline, not the current worktree and not implementation-worker output. Workers must check for later user changes before touching affected files.

| Input | SHA-256 |
| --- | --- |
| docs/implementation/real-service-verification.md | f4ce05bacdcee8671e96651b045d74cf1f825ae16d8c3385b9afabcb0c10dc50 |
| docs/implementation/README.md | 57d740da9c5abe9bddca308d09674e9726bbeb737f299e725cc5f2494ca1b780 |
| docs/implementation/architecture.md | aad2891cef8831f80fb71bd275b96910e4ffc861136c39afd4348fc5987ac6b7 |
| docs/implementation/http-api.md | a125ad27d4523d6abdd4f39b5a379c19b32dff8b078e202c85a46bffe9429aa2 |
| docs/implementation/independent-testing.md | c8f78ab266beb931c4d6ec306d592af6ea3439379ab8bfc4beebd04b88038115 |
| docs/implementation/shared-interfaces.md | 3b47a08a67145a8190287cf92d45f904996793fa330791833e57fefb9026f297 |
| docs/implementation/worker-a-evidence-platform.md | 262dcfe3533042cd72459aa31066357238dcbae44dc8ab83292b40be50c9294f |
| docs/implementation/worker-b-intelligence.md | 87f2ae6bbb951c5b88fb0a57aac5e9c4747568d7fee71219c3299b87492af503 |
| docs/implementation/worker-c-product.md | 6a2b0eeed6868589b3d25be566676fe7d17e9063fb502b91321d2fe4c9a020c5 |
| docs/implementation/contract-examples.json | 1b0b0c43a2842c93c9d85c1d5dd87060c018827bcfe42f0fe9c955589f5375d8 |
| docs/production-behavior.md | 8dee98c55acd566612dba1a65c096e5401edadc1746d77eca9175303191e6825 |
| docs/ai-agent-architecture.md | 78610a73ef68d218b7c4083516ac76273aa042a082850649f7ffdf504a830952 |
| docs/user-features.md | 4dba75ca5b900560526dbe1aad179c1dbf6063ad8aefc9b55a4d55a0ece10a18 |
| docs/user_ui.md | 04faef9fc8f3bd8fd9f28885fcde4a4dd77468de46ca916d1e3f4d8f699e67bd |
| docs/database.md | a0e4907edbb3b9b11b82ac4b863702e034007864de0cb46bd20da3cbb82d048c |
| docs/Pseudo-AI-agent.md | 1350b4b900b78d322597ab9f67a4185ceaa1c7b582eb4e32fd939a5c2c825244 |

Inherited git status:

```text

```

