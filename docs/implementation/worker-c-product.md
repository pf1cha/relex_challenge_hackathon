# Worker C — browser product, API composition and acceptance

Read `README.md` and `architecture.md` first. Sources: all of user-features, production behavior §§3-4, architecture §§5,9,11-12. Own `frontend/`, `backend/app/api/`, backend composition/entry points and the other C paths. Assemble A/B services; do not reimplement their authorization, retrieval, privacy or review logic in routes or TypeScript.

## C1 — runnable shell, login and contract adapters

Create dependency manifests, application entry point, environment example without secrets and startup instructions for the target project only. Wire A's migrations/bootstrap and durable job runner, and register B's handlers without circular imports. Load private configuration without printing credentials. Health reports actual database/index readiness; report model readiness separately rather than presenting connectivity as product completion. Services run within permitted compute allocations, with recorded job IDs/ports/data ownership and cleanup limited to owned processes.

Implement `backend/app/bootstrap.py` as the sole concrete A/B wiring location, `main.py` as the ASGI factory and `worker.py` as the durable job-process entry point. Own shared configuration, backend packaging, frontend package/build/typecheck scripts and generated OpenAPI client. Keep frontend source/assets/tests under `frontend/`; do not embed the application in backend HTML strings. Serve the compiled frontend or use a same-origin development proxy; no provider keys reach browser assets.

Implement routes in the shared contract with A session/authentication services. Include login/logout, filtered project selector and role-specific navigation. CSRF protection, server-side authorization and safe errors apply even when callers bypass the UI. Escape document/model text; do not render arbitrary source HTML. Development contract fixtures are replaceable adapters, visibly marked; never ship them as successful answers.

Acceptance: admin/member/outsider sessions, incorrect login, logout, project switch, direct URL access, CSRF rejection and app restart. Project B titles/counts/snippets never appear for project A-only users. Client/employee association does not create login membership. Record real service/model feasibility or a specific unresolved prerequisite.

## C2 — document upload, list, search and receipt viewer

Admin can upload supported text, inspect processing stages, see safe failed-state reasons and retry/remove failed uploads. Member sees eligible documents only. Implement search query plus type/date/person/source/topic filters using B's single search service. Show privacy-safe snippets and record expansion/loading states.

Source viewer opens at stable cited span, displaying safe original title, record date/type, context and highlighted supporting text. Citation icon next to each factual claim opens a quote popover/side panel on hover, keyboard focus and tap. Include source link opening a new tab (`noopener`); server reauthorizes it. Long records paginate without losing the cited span. Unavailable/version-changed receipts show a clear state and regeneration action, never old cached text.

Acceptance: browser upload to published list, malformed upload recovery, all filter controls, pointer/keyboard/touch-equivalent citation interaction, new-tab navigation and quote-to-source equality. Unauthorized new-tab URL access is denied. Verify a citation after redaction uses the sanitized current span or becomes unavailable.

## C3 — reviewed chat and project status

Submit questions with session/project context established server-side. Route B's reviewed candidate through A's atomic release-and-persist operation before returning. Save answer ownership/dependencies/generations through A repository. No factual draft streaming. Show processing, verified claims with individual receipts, inability/partial-coverage states, provider failure and evidence-changed retry. Implement owner-scoped conversations, message history and follow-up submission with conversation ID; invalidated previous answers render unavailable placeholders.

Conversation text is not new evidence. Later questions must still resolve to currently eligible sources. Reopening saved answers rechecks ownership, project permissions and dependencies. Clear project-specific UI state on project switch/logout. Treat browser caches as part of invalidation; use no-store for sensitive API/source responses. Already downloaded content cannot be remotely erased; do not claim otherwise.

Add visualization navigation with permitted-project selector and explicitly labeled document/processing status. Display that actual visualization content is deferred; do not invent an uncited graph to claim completion.

Expose the dependency-validated project overview as cited text with pending/rebuild state, separate from the visualization placeholder. Populate filters from the safe filter-options endpoint. Recover job progress after browser reload via the admin job list; do not rely on in-memory upload IDs.

Only render an overview's reviewed claims/receipts; pending or failed grounding displays status, not raw memory prose. Re-fetch answer receipts through the owner-scoped receipt endpoint before showing a popover. A stale version returns unavailable/regenerate; never attach a current quote to an old unchecked claim. Pass a stable request ID on chat retries, and load/authorize history server-side rather than accepting client-supplied messages as trusted context.

Acceptance: supported/unsupported/conflicting questions from B fixtures, incomplete record coverage and reviewer unavailable. Inspect API traffic to prove claims are returned only after review and final checks. Hold a response across A's privacy/activation/access change; show withheld-result UI. Saved answers cannot leak changed evidence. Project status counts obey eligibility and scope.

## C4 — admin lifecycle and end-to-end evidence

Admin controls activate/deactivate/delete documents, associate client/employee identities, manage user membership/roles and request project-local person erasure. Distinguish removing membership from erasing personal information. Destructive UI confirmation states exact project/person/document target. Show pending/running/failed/completed job state and safe retry action; do not label HTTP 202 as deletion complete.

Coordinate A/B fixtures for same-name people, failed upload, aggregate dependencies, multi-chunk repeated summaries and late corrections. The UI must show retained project decisions after erasure with `[deleted user]` attribution and current receipts. Disable inappropriate actions during lifecycle processing, with server checks remaining authoritative.

Acceptance: member cannot call admin routes directly; admin performs membership/association/document/person workflows; deactivation hides evidence and reactivation repopulates it only after coherent publication. Inject one deletion/index failure, observe failed status and unavailable evidence, retry and verify completed state only after A/B checks. Run actual browser interactions, not only curl or static HTML inspection.

Show the project write-barrier state during erasure: content-producing submissions return a retryable 409 and the UI preserves unsent input only in memory. Retest after reload using job status. Include logout during chat, another user's conversation ID, double-submit/retry, a stale citation popover and a delayed index write during erasure in integrated acceptance. Removing membership must not be mislabeled person erasure, and admin preview must not reactivate a source for AI use.

## Evidence checklist and handoff

Create synthetic fixtures only under `fixtures/implementation/`; preserve existing corpus. Own repeatable acceptance orchestration in `scripts/product/`. Coordinate exclusive verification project IDs so workers cannot delete one another's fixtures. Do not use hard-coded answer branches in application code.

Record in `evidence-c.md`:

- Revision and inherited dirty state; setup commands, configuration keys, ports/allocation IDs and browser access instructions without secrets.
- G1: login -> upload -> memory/index publication -> member source; outsider denied.
- G2: question -> retrieval/read/history -> independent reviewer -> final gate -> receipt -> authorized new tab; B chronology cases linked to evidence.
- G3: deactivate/reactivate/delete document and erase person, including failure/retry, old answer/source URLs and in-flight invalidation; A/B store-inspection evidence linked.
- G4: browser views/interactions, service persistence after restart, all worker acceptance case outcomes, unresolved gaps and exact visualization/provider-retention limitations.

No worker-authored report is proof by itself: retain safe observable results and distinguish expected from actual. Development checks with mocks do not pass live acceptance. When a prerequisite is unavailable, deliver completed code and an explicit unverified case list; never invent PASS.

> Implement Worker C in `/scratch/project_2020551/relex-0919` using this file and the shared README. Start C1 and browser states against shared contract examples while A/B work. Own route composition and runtime/dependency setup, then C2-C4 and shared G1-G4 verification. Use A/B services without duplicating business logic. Preserve inherited changes and source docs; do not dispatch descendants or change another checkout.
