# Worker A — evidence, access and privacy lifecycle

Read `README.md`, `architecture.md`, `shared-interfaces.md`, `http-api.md`, `independent-testing.md` and `real-service-verification.md` first. Sources: production behavior §§3-4; architecture §§2-3,9-11; database sketch as design input only. Own `backend/app/evidence/`, contracts and the other A paths in the ownership table. Deliver the canonical foundation B and C consume, not a parallel UI or answer agent.

## Verification policy: real services

Verification follows [real-service-verification.md](real-service-verification.md). Run the actual implementation against real PostgreSQL, Qdrant, configured model/reviewer/embedding services, FastAPI and a browser wherever the required operation uses them. Synthetic input documents are encouraged; fake service responses are not acceptance evidence.

Contract tests, schema examples and fixture-service scenarios below are development aids. They may establish implementation readiness but cannot mark product behavior verified. Cross-slice live checks stay pending until real adapters are available. Independent code handoff remains allowed, explicitly labeled implementation-ready rather than live-verified; missing services are reported as blockers, never replaced by a mock pass.


## S-A — independent development and live component verification

Implement A1-A4 while B/C work independently. Use the G0 contracts and `independent-testing.md`. Own fixtures under `backend/tests/evidence/` and a runner under `scripts/evidence/`; maintain shared adapter-driven conformance cases under `backend/tests/contracts/`.

Run real A services, migrations and durable jobs against isolated real PostgreSQL. Use A's direct PostgreSQL driver adapter and the local connection settings in architecture.md; a hosted database API is not required. A standalone tests use their own database/schema and can connect without C's server/bootstrap. Inject controllable B processing/rebuild/index-removal callbacks which return contract-valid artifacts and can fail, pause or report unknown write outcomes. Supply reviewed candidates at the contract boundary to exercise real A release transactions, exact quote/digest checks and races. No B/C implementation, model service or Qdrant is required for S-A. Optional model-assisted privacy detection uses a detector substitute for deterministic cases, with real detector checks reported separately.

Cover auth, source versions, job restart/retry, publication, privacy inventory and write barriers. A substitute index is a development aid only; verify claimed index lifecycle behavior through real Qdrant/B execution under G3/G4. Record these separately.

## A1 — authenticated project boundary and contract implementation

Use the G0 typed DTOs/protocols and implement migrations, session/password service, projects and memberships. Provide an explicit user/project bootstrap CLI without default passwords. Bind access to the authenticated user; membership role is project-scoped. Personnel and login users are separate entities. Project membership changes increment access revision and invalidate affected in-flight releases. Prevent accidental removal of the last admin unless an explicit transfer workflow exists.

Define canonical documents, records/versions, spans, restricted identities/contact aliases, occurrences, memories/dependencies, jobs/outbox, answer dependencies and generations. JSONB is acceptable for summary prose/metadata; enforce project references and version constraints in repository operations. Preserve unknown dates/identity matches rather than fabricating values. Make schema migrations repeatable.

Acceptance: two projects with admin/member/outsider accounts; exercise every repository read against unauthorized context. Same document ID in wrong project never resolves. Member cannot mutate membership or view restricted identity mappings. Logout invalidates the session. Existing database survives app restart and repeat migration.

Handoff: typed contract imports, bootstrap instructions and seeded synthetic project IDs. B/C can proceed against these contracts immediately.

Use shared contract revision 5 from `shared-interfaces.md`, including its begin/release/fail chat attempt sequence, exact DTOs and index-operation ledger. Include session identity in request context, caller-owned conversation lookup, atomic `release_answer`, restricted JobCapability and index-operation acknowledgement ports. Receipt resolution uses exact versions; changed receipts return unavailable rather than being silently remapped.

## A2 — upload to sanitized source

Implement durable import jobs and supported text parsers. Split bundled emails into records; preserve report/transcript boundaries and original locations. Quoted `From:` lines are not automatically new messages. Preserve speaker and quote provenance; track duplicates so B can avoid independent corroboration. All accepted source text must be accounted for as source content, headers or explicitly removed sensitive spans; parsing cannot silently drop tails.

Detect identities and contacts before memory/embedding calls. Assign project-local opaque IDs. Keep customer organizations separate from people; do not merge same-name people automatically. Use rules/entity detection and a configurable model adapter if required; quarantine ambiguous cases. Restrict raw/intermediate content. Preserve operational dates/actions when removing private context without inventing replacement facts.

Expose current sanitized record pages and stable span resolution through A ports. Preserve safe original title/identity. Provide a separate job-capability read for sanitized staged versions so B can extract/index before publication; user-facing and agent reads cannot use it. C registers B processing handlers through the shared interface; records become published only after required memory/index work succeeds and A verifies versions. Recovery must survive process restart rather than depend on an in-memory thread. Implement the revision 5 load/stage checkpoint ports and CT-17: persist the exact ArtifactBatch before index work, reload it under a valid replacement lease, and deny checkpoints invalidated by erasure/source changes. Persist job leases, stage idempotency keys, retry state and safe progress; reclaim expired leases after crashes.

Acceptance: bundled emails, quoted forwarding, transcript turns, standalone report, unknown dates, duplicate input, malformed input and two same-name people. Verify source boundaries in SQL. Assert downstream maintenance/answer/reviewer/embedding input capture for synthetic fixtures contains no original names/contacts; any model-assisted privacy detector is a separately restricted preprocessing operation as described in architecture.md. Inject failure after index write but before SQL publication; stale index candidates remain inaccessible and retry produces one current version.

## A3 — lifecycle, invalidation and release gate

Implement centralized eligibility with explicit `answer_evidence` and `admin_source_preview` purposes as defined in the shared README. Use it for source/receipt access, saved answers, B retrieval and C status; admin previews do not authorize inactive sources in answers. Provide atomic final validation plus answer persistence, with the transaction commit as the release linearization point. Mutations committed before it withhold obsolete content; subsequent reads revalidate. Do not hold transactions across network delivery.

Persist caller-owned conversations/messages, answer dependencies and source-linked project overview artifacts. Scope every conversation to its owner and project; invalidate cached answers on corpus changes, including newly ingested corrections. Provide query/history normalization without exposing identity mappings to B. All conversation text and titles belong to the person-erasure inventory.

Deactivation first makes documents and dependent aggregate memories ineligible, increments generation, then schedules B rebuilding from active sources. Reactivation rebuilds required artifacts before publication. Permanent deletion removes application-owned source and derived content, Qdrant entries through B, saved answer material and restricted pending uploads. Failures stay visible and do not expose old sources. Job IDs and safe audit counts may remain without deleted content.

Acceptance: mutate one source of a two-record topic summary; the old aggregate disappears immediately, unrelated records remain usable, and rebuilt summary uses only eligible sources. Hold chat and source requests across membership revocation/deactivation; obsolete responses are withheld. Old source URLs cannot reveal former versions. Reactivation restores only coherent versions.

Verify logout during a running answer prevents release; another user's conversation ID fails before B runs; a repeated request ID returns one persisted turn. Test unrelated record publication leaves existing valid vectors eligible while invalidating old saved current-state answers. Base-record publication marks aggregates pending without waiting for those aggregates to build from the record being published.

## A4 — resumable person erasure preserving facts

Authorize explicit project/person scope. Persist an occurrence-based inventory and affected IDs before removing mappings. Include retained uploads, raw/intermediate/current/old versions, filenames/headers/metadata, identities/contact aliases, source spans, memories/change notes, chats, caches, jobs and content-bearing logs. Coordinate B's index deletion/re-embedding through durable stages. Quarantine affected evidence and bump privacy generation before cleanup begins.

Replace selected person's names/contact occurrences and opaque references with `[deleted user]` where attribution is required, retaining decisions and actions. Do not globally replace an ambiguous shared name. Unattributable occurrences keep affected records unavailable until admin removes/corrects the input. Keep restricted cleanup material only while required for retry, and erase it before completion. Audit by operation ID/counts, never `purged_name`.

Call B to regenerate changed memories/embedding inputs, remove obsolete entries and report input hashes/model calls. Verify all controlled stores and current sanitized receipts before marking completed. Failed jobs resume the same inventory; untouched records and vectors remain unchanged. Report backup/provider limits separately from controlled-store completion.

Implement the project write barrier and compare-and-set job fencing from architecture.md. Inventory queued/staged uploads and outstanding index operations, not just published records. No completed erasure while an old worker can still recreate an obsolete point or chat. Keep failed cleanup resumable; lift the write barrier only after drain/reconciliation and final verification. Treat unknown network-write outcomes as unresolved, not successful cancellation.

Acceptance: two people named alike with different contacts/actions; erase only one. Preserve the other's attribution and both supported operational facts. A changed record-level summary repeated in multiple embedding inputs triggers recomputation of all those entries. Inject failure halfway, restart, retry and verify no duplicate current vectors, no old-content resurfacing, no completed status before cleanup. Include failed-upload raw text and persisted questions containing the target name.

## Done and dispatch prompt

Record A1-A4 evidence in `evidence-a.md`, including SQL/Qdrant versions, job IDs, interruption point and observed recovery. Unit checks alone do not establish erasure. Coordinate fixture IDs with C and handler signatures with B.

> Implement Worker A in `/mnt/relex-kai` using this file and the shared README. Start from G0 contracts; implement A1-A4 and run S-A independently while B/C implement their slices. Preserve inherited changes and source docs. Own only A paths; request cross-owner changes. Verify access, publication and erasure using synthetic data and real stores. Record failures honestly; do not dispatch descendants or change another checkout.
