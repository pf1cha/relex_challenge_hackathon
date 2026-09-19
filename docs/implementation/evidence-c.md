# Slice C evidence

Frozen delivery specification: revision 4. Shared service contract: revision 5.
Baseline: `2063eba9b3f9619653a5b1640b2e87ce725b1c4d`.
Authoritative checkout: `verda:/mnt/relex-kai`.
Implementation commits: `1471370`, `26e7f6a`; later focused changes are recorded below.

C confirmed the baseline, remote cwd and frozen status before editing. Inherited implementation-document changes were preserved and excluded from implementation commits. No private `.env`, source corpus, historical source specification or another owner's implementation was edited. A/B boundary defects discovered through real browser flows were repaired by their owners.

## Implementation

C1: actual FastAPI routes with injected `Services`; explicit public DTO response models; trusted-origin/session-bound CSRF; safe fixed errors; secure cookies unless explicit loopback HTTP; no-store responses; local PostgreSQL configuration; sole A/B composition root; independent HTTP and durable-worker processes. Credentials stay in backend private configuration.

C2: UTF-8 bounded uploads, document records, safe job progress, all shared filter controls, canonical source viewer, centered source pagination, location labels and highlighted receipt spans. Citation hover/focus/tap always fetches the current owner-scoped receipt; links open separately authorized source pages with `noopener`.

C3: server-controlled begin → intelligence → atomic release flow, no unchecked candidate serialization or draft streaming; stable request IDs for transient retry; owner-scoped history, unavailable placeholders, partial/inability outcomes, overview review states and explicitly deferred visualization. Project/session/view changes fence late UI results. Private content uses no browser persistent storage.

C4: project member role changes, exact-ID person associations, same-name disambiguation through IDs, document activation/deactivation/deletion, exact-target confirmations, erasure versus membership distinction, durable job rediscovery/retry and write-barrier status. Completed processing refreshes the document list.

Types in `frontend/src/api/schema.d.ts` are generated from the actual route OpenAPI export. `create_app` imports no concrete A/B implementation or private configuration. Explicit synthetic substitutes live only under `backend/tests/product/`.

## Real runtime and ownership

- Python 3.12.14 in `.venv-c`, project-local uv under `.tools`; Node 22.14.0 under `.tools/node-v22.14.0-linux-x64`.
- FastAPI 0.141.1, Pydantic 2.13.5, psycopg 3.3.6, psycopg_pool 3.3.2; HTTP and worker each own a lazy native connection pool.
- Chromium 153.0.8010.12 under `.tools/browsers`; Playwright drives actual compiled browser pages and API traffic.
- Owned PostgreSQL 18.6 at `127.0.0.1:15432`, database `postgres`, user `relex_dev`, persistent `.runtime/c-postgres/data`, process user nobody. Loopback trust is restricted to this synthetic development cluster; no host service/package changed.
- B-owned Qdrant 1.14.1 at `127.0.0.1:16333`, persistent B runtime; each run uses a distinct collection.
- Actual configured generation `gpt-5.4-mini`, embedding `text-embedding-3-small`, observed dimension 1536. All inputs were synthetic.
- C runners create `c_live_<run_id>` schemas/collections, random loopback HTTP ports, synthetic accounts/projects and owned HTTP/worker PIDs. They stop only their processes and retain owned state for inspection.
- `.runtime/c_<run_id>/private.json` contains synthetic account credentials and the private session secret, mode 0600; it must not be committed or copied into reports.

## Commands and observations

```sh
.venv-c/bin/python scripts/product/export-openapi.py
cd frontend
PATH=/mnt/relex-kai/.tools/node-v22.14.0-linux-x64/bin:$PATH npm run generate
PATH=/mnt/relex-kai/.tools/node-v22.14.0-linux-x64/bin:$PATH npm run build
cd ..
bash scripts/product/test-slice.sh --run-id cdev
RELEX_DATABASE_URL=postgresql://relex_dev@127.0.0.1:15432/postgres \
RELEX_QDRANT_URL=http://127.0.0.1:16333 \
bash scripts/product/verify-live.sh --run-id cfifth
# csixth ran concurrently using the same command with its own run ID.
.venv-c/bin/python scripts/product/verify-concurrent.py
```

Build/typecheck, actual inert factory import, one focused transport development check and the explicit fixture-browser login/logout all passed. These are development evidence only.

Two actual product runs `cfifth` and `csixth` overlapped with disjoint schemas/collections and ports 46643/34511. HTTP/worker PIDs were 32706/32707 and 32825/32826. Their main browser, restart and lifecycle drivers passed; runners returned 2/PARTIAL to retain remaining acceptance obligations.

Observed on both real runs:

1. Incorrect password, real login, project selector, missing-CSRF 403 and unsupported query 422.
2. Invalid UTF-8 upload 422 with safe browser error, followed by a valid upload on the same form.
3. Actual durable worker/model/index publication; canonical PostgreSQL records; browser reload rediscovered jobs/documents.
4. Exact identifier hybrid search, date/type/document filters separately and combined, centered canonical source pagination.
5. Actual generation and independent review released claims only through A; exact receipt quote; pointer/keyboard/tap preview; new-tab canonical source highlighting.
6. Same request replay returned the same answer ID; changed input returned idempotency conflict.
7. Separate real member/outsider browser sessions: member admin call 403, another owner's answer 404, outsider project list empty and source 404.
8. Deactivation confirmation and asynchronous job; old receipt 410; history shows unavailable rather than old answer content.
9. HTTP and worker restart preserved documents, conversations, jobs and sessions; browser project switch cleared unsent question/state.
10. Membership grant/removal and exact-target confirmation, separate from erasure.
11. Two same-name identities received distinct IDs; UI erased one exact ID and left the other.
12. Reactivation rebuilt eligible sources; document deletion completed through actual worker/index cleanup.

For cfifth: project `ef7170a3-0d2b-47cd-8934-f13a737e0df3`, document `74adbeb3-3155-4181-a622-3fb616539a37`, answer `8fa59ca0-56bb-4125-9524-b1e084526f75`.
For csixth: project `e3d053bb-6129-4290-9bd6-fd512de46d25`, document `b86bd9d9-d0d5-4bf3-8782-f389a33afcbe`, answer `b377c7ff-b956-4edf-a84f-a92e7de49399`.
Final persisted inspection on both: documents/records/checkpoints/current entries zero, Qdrant points zero, write barrier false. Superseded aggregate jobs may remain failed with no content; cleanup itself completed.

Safe observable artifacts:
- `.runtime/c_cfifth/{report,browser,restart,lifecycle}.json`
- `.runtime/c_csixth/{report,browser,restart,lifecycle}.json`
- `.runtime/c_cg4_20260919_091050/provider-failure.json`
- `.runtime/c_c_job_retry2/job-{failure,recovery}.json`

Focused real worker failure/retry:
```sh
PATH=/mnt/relex-kai/.tools/node-v22.14.0-linux-x64/bin:$PATH \
PLAYWRIGHT_BROWSERS_PATH=/mnt/relex-kai/.tools/browsers \
RELEX_RUN_ID=c_job_retry2 \
RELEX_DATABASE_URL=postgresql://relex_dev@127.0.0.1:15432/postgres \
RELEX_QDRANT_URL=http://127.0.0.1:16333 \
.venv-c/bin/python scripts/product/verify-job-retry.py
```
Exit 0. Actual generation endpoint outage produced persisted failed/retryable job `bcda3e68-2381-47e0-815b-011361e47dc2`; browser rediscovered it and offered retry. After restoring the actual worker provider, clicking retry completed the same job and refreshed the published document list without a browser reload.

## Concurrency

`.runtime/g4_20260919_091307/concurrency.json` records actual simultaneous A/B/C live commands at 09:13:07 UTC, with separate runner resources:
- A `ag4_20260919_091307`, PID 44497, exit 0 after basic/advanced/source real checks.
- B `bg4_20260919_091307`, PID 44498, selected B-C1, exit 3 (executed, semantic acceptance review pending).
- C `cg4_20260919_091307`, PID 44499, exit 1 from the explicitly recorded long-fixture budget outcome below.

This proves real service overlap/resource isolation, not a full product pass. Individual behavioral outcomes remain authoritative. A/B final acceptance maps are in their owned evidence reports.

## Failures retained and repaired

- cfirst exposed duplicate chat forms from overlapping view renders and raw stale-state wording. C fixed per-view generation fencing and unavailable guidance; csecond and later runs passed.
- cthird initially exposed a FastAPI shutdown-hook API mismatch. C switched to lifespan cleanup. Its subsequent malformed-upload probe exposed an unset select default; C fixed valid first-option selection.
- cfourth exposed A's completed-deactivation document remaining processing=pending, blocking legitimate UI actions. A fixed lifecycle document state; cfifth/csixth verified reactivation.
- The first G4 run proved actual provider outage -> safe 503/retry UI, then recovery exposed B drafting an unsupported no-reference clause for an empty corpus. B now returns fixed no_evidence after canonical retrieval confirms no spans. The failed result was not passed off as successful review.
- The second G4 C long semantic fixture exhausted B's budget and returned empty review_rejected with explicit partial coverage. It was safe withholding, but failed the positive-answer assertion. The detailed artifact remains. Browser pagination input was separated from this semantic stress case; B's own long-record matrix remains required.
- cfinal's blank-line source input exposed A requiring a chunk interval for empty source spans. A fixed character coverage for nonempty spans; B also preserves zero-length span slices. No source text was discarded. Fresh focused actual blank-line answer 8e468169-9e81-4384-8165-9d811905967b released two claims with complete coverage and no limitations; .runtime/c_cfinaltwo/blank-source-recovery.json. B also fixed duplicate complete-record rereads that consumed budget.
- The first focused job-retry harness read the previous failed state before the retry HTTP response committed. The harness now awaits the real retry response; c_job_retry2 passed.

## Requirement/scenario map and limits

| Requirement/scenario | Current observed evidence |
| --- | --- |
| R-G0 independent imports/routes/client | Import and development browser passed without concrete A/B loading; generated client build passed |
| R-C1 sessions/roles/projects/incorrect login/logout/direct URL/CSRF/restart | Real cfifth/csixth plus restart artifacts |
| R-C1 personnel association must not grant login membership | Canonical separation belongs to A; C exposes separate controls and real membership checks |
| R-C2 upload/progress/malformed recovery/current source | Real browser+SQL/index publication and rejected malformed input |
| R-C2 filters | Real date/type/document and combined requests; person/topic semantic filtering linked to B's matrix |
| R-C2 hover/focus/tap/new tab/quote equality/unauthorized source | Real Chromium flows above |
| R-C2 long source browser pagination | cfinalthree actual next/previous source pages and return to highlighted quote |
| R-C2 after redaction | A real erasure/source evidence plus C late-writer source/browser probe below |
| R-C3 reviewed claims, inability/partial/provider failure, saved owner history | Real release/receipt flow; actual safe budget withholding and provider503 observed |
| R-C3 stable retry/different key input | Real same-answer replay and409 idempotency conflict |
| R-C3 project switch/logout/state clearing/restart | Real browser and process restart observations |
| R-C3 logout/access/source mutation in-flight | c_races3 actual browser pauses after provider/review: logout, revocation, source mutation all passed |
| R-C3 overview/visualization | Implemented reviewed-only overview states and explicitly deferred visualization; full semantic overview evidence belongs to A/B |
| R-C4 membership/association/same-name erasure/document lifecycle | Actual browser admin flows above; exact IDs confirmed |
| R-C4 failure/retry/reload | Actual failed worker provider, persisted job rediscovery and successful same-job retry |
| R-C4 write barrier/late index completion | c_late1 actual tracked writer pause, failed cleanup/barrier, browser retry and completed cleanup; linked A advanced evidence |
| R-S two live instances | cfifth/csixth ran concurrently in distinct resources |
| R-G1/R-G2 | Real browser upload -> persisted/source/index and answer -> independent review -> atomic release -> receipt |
| R-G3 | Real UI lifecycle and SQL/index cleanup; full changed-person content/late writer/failure matrix linked to A/B |
| R-G4 | Actual process persistence, browser states and three-runner concurrency; independent review and full source acceptance still required |

Status: **implementation-ready; extensive live behavior verified; overall acceptance pending**. Do not call every matrix row live-verified before independent semantic and spec review is complete. No unavailable service was silently replaced by a mock.

Actual visualization content remains deferred. Application-controlled erasure does not include already downloaded browser pixels/files, the external source corpus, backups or provider retention. No full GDPR-compliance claim is made.

## Final focused verification

The complete C run **cfinalthree** passed all executed browser, restart, lifecycle, provider-failure and provider-recovery drivers. The outer runner retained exit 2/PARTIAL for full acceptance review. It used schema/collection c_live_cfinalthree, project 42ba9310-9529-44ab-949d-c91e6799634e, port 40113 and initial HTTP/worker PIDs 56714/56715. Reviewed answer 25411b40-a989-41bf-84f3-4bdf672feb90 had actual receipts; after an actual embedding-endpoint outage, restoring the provider and retrying the identical request released answer a5283cda-fb70-4ea6-a661-f3bb22714b9c. Long source next/previous pages and return to highlight passed. Artifacts: .runtime/c_cfinalthree/{report,browser,restart,lifecycle,provider-failure,provider-recovery}.json. Final canonical source/checkpoint/current-entry and Qdrant counts were zero, barrier false.

**c_races3** exited0 with real HTTP/browser/PostgreSQL/Qdrant/providers and actual reviewed candidates. Test-only pauses delayed release after actual B answer work, without supplying a canned answer or review:
- duplicate while the original request was held returned 409 request_in_progress; original released 200;
- project switching discarded the late old view;
- logout revoked the session and retained login UI during late completion;
- membership revocation before release returned 404;
- source deactivation before release returned 409 evidence_changed;
- the saved receipt returned 410 and browser retained no old quote.
Artifacts: .runtime/c_c_races3/{browser-races,race-stores}.json. Project 30cf4984-cb42-4911-9e2f-4fea84154646. The earlier c_races2 harness incorrectly selected the duplicate response instead of the original response; this was corrected to bind the original browser Request object. Actual stores had correctly persisted the original answer.

**c_late1** exited0. Two actual workers processed an upload and person erasure while a test-only pause held the tracked real Qdrant upsert. Cleanup job b9c14ad2-79a0-489f-a208-ab4267e9503f failed retryably with index_outcome_unknown and retained the write barrier. Browser reload displayed the barrier and disabled upload/chat while preserving an unsent question. Releasing the actual writer then clicking the persisted job's retry completed cleanup and cleared the barrier. Canonical source excluded the erased synthetic identity. Direct actual Qdrant lookup of obsolete entry 75b739d7-4812-5d84-b29e-8f9c5858e792 returned an empty result; a sanitized replacement entry remained. Artifacts: .runtime/c_c_late1/{browser-late-writer,race-stores}.json.

Reproduce focused races with the same database/index environment as the standard live runner:
```sh
PATH=/mnt/relex-kai/.tools/node-v22.14.0-linux-x64/bin:$PATH \
PLAYWRIGHT_BROWSERS_PATH=/mnt/relex-kai/.tools/browsers \
RELEX_RUN_ID=unique_races .venv-c/bin/python scripts/product/verify-browser-races.py
# For the late-writer/browser-barrier driver also set:
# RELEX_BROWSER_DRIVER=scripts/product/browser-late-writer.mjs
```

A's complete canonical source/privacy/release/checkpoint/crash/late-writer evidence is in [evidence-a.md](evidence-a.md), final implementation 4950e1c. B's provider/index/review/semantic evidence is in [evidence-b.md](evidence-b.md). The combined concurrency artifact above remains a truthful mixed-outcome overlap run; these subsequent focused results repair and verify its identified behavior without rewriting it as an all-pass run. No service dependency is currently blocked; independent review remains required.

A follow-up actual browser reopening of retained c_late1 data passed: the canonical source viewer displayed [deleted user] and the preserved Finland action while excluding the original synthetic name/contact. Artifact: .runtime/c_c_late1/redacted-source-browser.json. The first added browser locator incorrectly selected a hidden Load more control; fixing the harness to select the record-title button resolved it.

A repeated late-writer probe **c_late2** must remain a failure: expected index_outcome_unknown/barrier behavior passed, but the subsequent actual provider-backed erasure rebuild failed nonretryably with contract_violation. Job 8f71c03e-2efa-44ef-9d38-c92d8236af53, schema c_live_c_late2. This does not invalidate the successful observed c_late1 sequence, but does prevent claiming deterministic repeated live acceptance. B was notified for owner diagnosis; no candidate or provider response was replaced with a fixture. Artifacts: .runtime/c_c_late2/{browser-late-writer,race-stores}.json. Independent review should assess this remaining B/A integration reliability issue.

Final C source checks: frontend TypeScript/Vite build passed; Python compile check passed; git diff --check passed. All C-owned HTTP/browser/worker verification processes stopped. The shared authorized project-local PostgreSQL/Qdrant services and isolated run state remain available.
