# Real-service verification

Verification policy revision 2 — 2026-09-19. Required by delivery spec revision 4 following the user's instruction to verify implementation by running real services instead of contract tests. No service is claimed to be running or implemented by this document.

## What counts as verification

Run the actual product and inspect its observable outcomes. Use real PostgreSQL persistence, real Qdrant indexing/retrieval, configured generation/reviewer/embedding endpoints, the actual FastAPI routes and an actual browser for browser behavior. A reviewer may use focused independent API/service probes, but browser requirements need browser execution.

Synthetic documents/accounts/projects are safe input data, not fake services. Contract tests, mocked repositories, fixture API responses, stub reviewers, fake embeddings, static inspection and health checks alone do not pass a behavioral requirement. They remain optional development aids.

Independent work and code handoff remain possible: use implementation-ready for completed code awaiting dependencies, live-verified for behavior actually observed on real services, and live-verification-blocked when a specific prerequisite is unavailable. No unfinished other slice prevents code handoff, but it can leave real verification pending. Do not call the entire slice verified while a required real path is unexecuted.

## Setup and ownership

- C owns repeatable runtime setup, backend/app/bootstrap.py composition and the integrated live runbook/runner. A owns migrations and the account/project bootstrap CLI under scripts/evidence/, plus database behavior. B owns model/Qdrant adapters and processing. A never edits C's composition file.
- Use local PostgreSQL on the backend host through A's native driver. HTTP and durable worker processes use the same configured application database. Use run-specific databases/projects/collections and persistent storage for restart checks.
- Confirm real generation, reviewer and embedding endpoints/model IDs/dimensions using synthetic probes. Models may share a provider while using separate contexts. No placeholder response is a substitute for unavailable credentials/services.
- Start the actual HTTP application, durable job process and compiled frontend or development frontend with same-origin proxy. Record commands, process IDs and ports without secrets. Use an authorized browser route to the running application.
- Required live commands, from repository root: `bash scripts/evidence/verify-live.sh --run-id <id>`, `bash scripts/intelligence/verify-live.sh --run-id <id>` and `bash scripts/product/verify-live.sh --run-id <id>`. C's product command orchestrates the assembled application/browser flows; A/B commands exercise their owned real components and use real cross-slice adapters whenever the checked operation requires them.
- These commands are required artifacts, not commands verified to exist today. Unlike development test-slice runners, live runners may depend on other completed slices. They must never switch to fixture composition. Missing dependencies produce nonzero status and explicit BLOCKED requirement IDs.
- Each live runner supports isolated run IDs, records which behaviors actually executed, and documents startup/cleanup. Scripts automate real service requests, browser actions and state inspection; they must not merely invoke a contract-test suite and rename its output live verification.
- Clean up only resources created by this verification run. Preserve the source corpus, existing application data, other workers' services and private configuration.

## Required live flows

| ID / requirements | Execute | Observe and record |
| --- | --- | --- |
| LIVE-01 / R-A1, R-C1 | Bootstrap admin/member/outsider on real PostgreSQL; log in/out in browser; bypass UI with direct unauthorized calls | Session persistence/revocation, project filtering, denied mutations/sources, real SQL state |
| LIVE-02 / R-A2, R-B1, R-C2, R-G1 | Upload synthetic bundled emails/transcript/report through the browser; let actual worker, model and embedding/index adapters finish | Real job transitions, canonical spans and sanitized inputs, Qdrant entry IDs/model/dimension/hash, published member source; outsider denied |
| LIVE-03 / R-B2, R-C2 | Search exact identifier and semantic paraphrase; apply each filter and read a long record with late qualification | Actual PostgreSQL lexical/Qdrant semantic results; canonical eligibility and ordered complete record coverage |
| LIVE-04 / R-A3, R-B3, R-B4, R-C3, R-G2 | Ask B-C1..9 questions through actual chat using fixed synthetic evidence; follow receipt into a new tab | Real retrieval/reviewer calls, supported claims, exact source quotes, decision chronology, persisted answer/ownership and absence of unchecked drafts |
| LIVE-05 / R-A3, R-C3 | Retry the same chat request; change its input under the same key; revoke access/logout/deactivate a source while a request runs | One committed turn, correct conflicts, no late release after mutation, stale answer/receipt unavailability |
| LIVE-06 / R-A2, R-B1 | Stop the actual worker after checkpoint commit; restart before index dispatch; repeat after real index acknowledgement before SQL publication | Reloaded exact checkpoint, no repeated maintenance generation, reconciled operations, one current published version/index entry set |
| LIVE-07 / R-A4, R-B4, R-C4, R-G3 | Deactivate/reactivate/delete a document and erase one of two same-name people through admin UI | Real source/derived SQL and Qdrant changes; preserved decisions, sanitized receipts and unaffected person's data; no premature completion |
| LIVE-08 / R-A4, R-B4, R-C4, R-G3 | Pause a real adapter write, start erasure, then release it; interrupt a dependency and retry cleanup | Barrier/failed/pending state, recorded unknown/late outcomes, actual obsolete-point removal and completion only after verification |
| LIVE-09 / R-C3, R-C4, R-G4 | Reload browser, switch projects, open stale popover, restart HTTP/worker processes against persistent storage | Job rediscovery, no cached cross-project content, durable conversations/state and correct unavailable/regenerate UI |
| LIVE-10 / R-S, R-G4 | Run two isolated instances of each owned live runner; separately run A/B/C live runners simultaneously when their real dependencies are ready | Disjoint database/schema/collection/ports/artifact names and cleanup; fixture/test-slice concurrency does not pass this check; pending checks never block code handoff |
| LIVE-11 / R-A3, R-B4, R-C3 | Exercise real reviewer rejection using unsupported/stale drafts and actual evidence; deliberately make an owned provider route unavailable, exhaust configured budgets, and submit altered receipt/digest inputs to the real release service | Independent reviewer searches/verdicts, safe failure or reviewed partial answer, rejected altered candidates and no unchecked factual response. Restore the real dependency and show successful recovery |

The LIVE rows group execution sessions; they do not replace any A1-A4/B1-B4/C1-C4 or CT-01..17 behavior. Each worker's evidence report maps every source acceptance scenario to a concrete live observation or an explicit pending/blocked entry. No scenario is satisfied just because its grouped LIVE session ran.

For negative-path probes, controlled fault injection may pause a real operation, stop an owned process/dependency, reduce budgets or feed malformed synthetic input. Recovery must still execute real adapters and persistence. Do not test deletion by returning a synthetic successful removal acknowledgement. For release-only probes, start from a candidate produced by the real B workflow and deliberately modify the specific field under test; a fabricated passing reviewer result cannot establish successful product behavior.

## Evidence and completion

For each requirement, record the tested revision, exact command/action, timestamp, service versions/model IDs, safe resource IDs, observed API/browser result, SQL/Qdrant state where relevant, and PASS/FAIL/BLOCKED with reason. Keep credentials and raw personal information out of logs. Screenshots complement persisted/service evidence; neither screenshots nor worker assertions alone prove cleanup or grounding.

A/B record evidence in their own reports; C links it from the integrated report. The independent reviewer inspects the diff and uses focused live probes to corroborate critical behavior. Do not repeat whole suites or add unrelated requirements.

If PostgreSQL, Qdrant, a provider, an implementation adapter or browser access is missing, name the exact missing prerequisite and affected LIVE/requirement IDs. Continue independent authorized implementation where possible. Never replace the missing real-service check with a passing contract test. Completion requires real-service evidence for all required behavior and bounded reviewer PASS.
