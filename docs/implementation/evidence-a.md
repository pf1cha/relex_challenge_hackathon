# Slice A evidence

Status: implementation-ready; owned R-A1–R-A4 live paths verified, 2026-09-19. R-S/G4 combined acceptance is recorded by C; independent review remains the parent gate.
Frozen delivery revision 4 / service contract 5. Baseline `2063eba9b3f9619653a5b1640b2e87ce725b1c4d`.
Inherited changes were coordinator specification files only. A did not edit/stage them.
G0 contracts checkpoint: `31d91d8`.

## Implementation

Native PostgreSQL, repeatable migrations and explicit bootstrap CLI; hashed passwords/session credentials and session-bound CSRF; project access epochs; privacy-safe source and exact receipt projections; restricted raw ingestion/identity normalization; canonical lexical retrieval and candidate validation; owner-scoped durable chat reservations and atomic reviewed-answer persistence; fenced jobs, exact staged checkpoints, external-write ledger and resumable erasure barriers. Imports are inert; concrete B handlers are injected.

## Real execution

Owned PostgreSQL 18.6 at `127.0.0.1:15432`, database `postgres`, role `relex_dev`; owned Qdrant at `127.0.0.1:16333`.
Generation/reviewer `gpt-5.4-mini`; embeddings `text-embedding-3-small`, observed dimension 1536.
Only synthetic inputs; no secret or private corpus logging.

Commands set `RELEX_DATABASE_URL=postgresql://relex_dev@127.0.0.1:15432/postgres` and `RELEX_QDRANT_URL=http://127.0.0.1:16333`.
- `bash scripts/evidence/verify-live.sh --run-id a3`: owned SQL/auth, real B upload/index/chat and lifecycle checks passed; exit 2 correctly reported then-pending advanced scenarios. Output `artifacts/evidence/a3/observations.json`.
- `PYTHONPATH=backend .venv-c/bin/python scripts/evidence/advanced_live.py --run-id advanced4`: exit 0. Output `artifacts/evidence/advanced4/advanced.json` and child provider-call traces.
- G0 imports of 82 DTOs/protocols and public example validation passed as supplemental development checks only.

| Requirement/scenario | Actual observation |
|---|---|
| R-A1 sessions, project boundaries, roles, last admin, logout, migrations/restart | a3 real SQL/session operations passed; adapter recreation retained state |
| R-A2 coherent publication | a3 real B maintenance, embeddings, Qdrant acknowledgements and canonical publication passed |
| CT-17 checkpoint before index | advanced4 schema a_adv_advanced4_checkpoint, job 891f3045-6bcf-450d-8e35-69eb3df13ebf: actual worker exit77, replacement process restored identical batch; resumed only embeddings |
| CT-17 ack before publication | advanced4 schema a_adv_advanced4_ack, job 0120f73e-614e-4885-a148-cd84a4b3fb0a: replacement process restored identical batch, zero provider calls, one current entry set |
| R-A3 / CT-01,02,05,06,07,08 | a3 real reviewed candidate persisted; altered digest rejected; owner denial; replay same answer; changed input conflict; exact receipts; logout/revocation/regrant/deactivation deny late release; stale receipts unavailable |
| R-A4 document lifecycle | a3 actual deactivate/reactivate/delete; coherent source visibility; completed deletion/barrier false |
| R-A4 / CT-15,16 | advanced4 job5fea40e3-54e3-4324-92b5-5994afea6ead: selected same-name identity removed, other retained, October decision retained, actual replacement vector/version2, raw inventory removed, in-flight chat blocked |
| R-A4 / CT-09,10 | advanced4 job518d054c-8129-4ec7-95e0-f2c710d94212: real upsert paused after dispatch, erasure failed at draining with barrier on, late outcome retained, real dependency interruption, same-job retry, obsolete point absent |
| R-A2 source-format/privacy matrix; R-A1 canonical read entry points | sources5 exit0: bundles, quoted forwarding, all input lines, transcript/report, duplicate lineage, unknown dates, malformed/PDF rejection, same-name quarantine; 19 canonical reads reject nonmembers; unchanged entries remain eligible and stale candidates/versions withheld |
| R-S / R-G4 | aisolated2 full command exit0 with disjoint schemas/collections. C owns final simultaneous A/B/C outcome; failures and earlier partial runs remain recorded rather than promoted to PASS |

## Failed attempts and repairs

Initial a1 failed provider availability because empty role-specific keys missed the already configured OPENAI key fallback; runner corrected.
advanced1 used too-short test leases for actual generation; corrected to15s.
advanced2 passed restart and same-name erasure, then exposed invalid model month-only dates; B now preserves unknown precision and safely rejects malformed outputs.
Late-write execution exposed inventory rolling back when a writer remained unresolved; inventory/draining now commit separately before external outcome checks.
C's browser found deactivation document metadata stayed pending; fixed and C verified two fresh real browser lifecycle runs.
source1 exposed false quarantine of normalized From headers; fixed. source2 exposed a test assumption about JSONB object order; source assertions now use canonical source line ordinals, and record list sorting uses explicit creation time/id.

The live runner now invokes advanced/source drivers itself; no contract-test or canned provider response marks a live requirement passed. Optional external privacy-detector execution is not claimed. Backups, external provider retention, unmanaged corpus and downloaded content remain explicit limits.


## Final focused results and mapping

- Full live command with run ID **aisolated2** exited **0** at 2026-09-19 09:17:58 UTC. Its observations plus **aisolated2_adv** and **aisolated2_src** retain exact IDs/results. This ran actual PostgreSQL, generation/reviewer/embeddings and Qdrant, not contract substitutes.
- **sources5** exited **0** on final native-pool code. Its transport wrappers asserted the synthetic original person's name/contact were absent before every actual maintenance, schema-repair, history-review, topic/overview, answer, reviewer and embedding call. One bounded real maintenance schema repair occurred and is retained in the call record.
- **advanced5** exited **0**. It repeated both actual process-crash checkpoints with exact batches/no maintenance regeneration, then verified failed erasure resumes in a **new worker process** against the real restored dependency. Late-write cleanup job: f22e7a50-5a58-4eb7-8173-18da68281f43. Old point b07b74b0-a3ee-590b-bb72-74472ce0acf1 is absent.
- **cap1** exited **0**: CT-13 wrong input hash and changed checkpoint metadata rejected; CT-17 lifecycle mutation rejects the old checkpoint read/write. These negative inputs were mutations of an actual B-produced checkpoint.
- **multi1** exited **0**: four chunks paged in order; stale continuation denied after erasure; every repeated-summary input hash changed; four real replacement vectors are present, four obsolete points absent, and an unrelated vector payload is byte-identical. Job 6f7e2a18-6555-42d9-a036-b05f66beac89.
- **lifecycle-duplicate** native PostgreSQL probe: repeated active DELETE returns the same durable job even after immediate visibility removal. Job 3272d2f5-90bd-4f67-b7fb-72125dc16712.
- Native PostgreSQL lazy pool migration twice/readiness/close succeeded in schema a_pool_probe. Multi1, sources5 and advanced5 subsequently exercised real operations through the pool.
- Compilation and owned-path git diff whitespace checks passed.

The default verify-live command now runs the main, advanced, source, capability and multichunk drivers. Each driver may also run independently with a unique ID. Evidence artifacts live under artifacts/evidence/<run-id>; additional state remains in matching a_live_, a_adv_, a_src_, a_cap_ and a_multi_ schemas/collections, retained for the independent reviewer. A started no host-wide service and cleaned no other worker's resources.

Detailed acceptance links:
A1 account/membership/session bootstrap, two-project boundary, member denial and restart are in a3/aisolated2; canonical per-method denial is sources5; actual browser transport/role flows are in C evidence.
A2 each supported format/provenance/duplicates/unknown dates/malformed and ambiguous inputs are sources5; actual downstream privacy assertions are sources5; publication and post-index crash recovery are aisolated2/advanced5; rejected malformed and stale checkpoints are cap1.
A3 exact quote/digest/replay/ownership and every required in-flight access/lifecycle race are a3/aisolated2; old source/version/cursor rejection is sources5/multi1; unrelated valid index entries survive additions (sources5) and erasure (multi1). Actual topic/overview review and boundary UI evidence are linked from B/C reports.
A4 exact same-name erasure, raw inventory removal, late queued writer, write barrier, safe failed state and new-process retry are advanced5; repeated-summary multi-entry replacement and untouched-record preservation are multi1; real document deactivate/reactivate/delete also passed C browser workflows. Original source corpus was untouched.

Additional repairs were validated through real execution: empty canonical spans remain in SQL/source views but no longer incorrectly require an embedding chunk interval; unknown date precision accepts a genuinely known timezone rather than inventing/rejecting one; duplicate active deletion remains idempotent; configured optional detector names must resolve to an existing association or remain quarantined. Optional external detector transport itself was not exercised or claimed as passed.

Earlier failed attempts are retained: sources3/aisolated1 failed closed on B maintenance schema validation; B added one bounded actual schema-repair call before checkpoint persistence. Successful later runs do not erase those observations. No broad full-suite run, provider fixture, fake embedding, canned reviewer or simulated successful index acknowledgement was used as acceptance.

## Independent-review repair — findings 1–3 (2026-09-19)

Reviewed frozen delivery revision 4, service contract 5 and the pinned requirements. Repair baseline HEAD was `1d9222da40358f1734e7bae3e634966956905115`; only A-owned implementation/report/probe files changed. No frozen specification, private configuration, corpus or other worker implementation was edited.

- **R-A2 / R-A4 / I-PRIVACY:** unresolved names in ownership/object positions and multiword name candidates now quarantine before maintenance/index calls. Alias-aware erasure inventory resolves source/title/raw occurrences against the restricted associations as well as opaque IDs; same-name ambiguity never becomes a guessed attribution. Cleanup normalizes legacy canonical aliases before replacement and verifies alias occurrences before completion.
- **R-A4 / R-C4:** cleanup failures at rebuilding with `contract_violation` are resumable, including already persisted failures created by older code. Public job projections expose corrected retryability without a GET mutation; authenticated retry keeps the same job/inventory/barrier and reruns validation.
- **R-A2 / R-A3 / R-C2:** lifecycle changes fence old leases/checkpoints, then schedule fresh authorized work for independently accepted ingestion/activation/deactivation. An unresolved old network write blocks replacement. Once settled, the replacement removes obsolete IDs through the real ledger/index adapter before writing. Its durable cleanup marker prevents retry from deleting a replacement that reuses an immutable ID. Superseded document metadata is coherent; erased restricted input is never silently reconstructed.

Focused commands (real PostgreSQL 18.6, Qdrant, gpt-5.4-mini generation/history review, text-embedding-3-small dimension 1536; same service addresses above):

```sh
RELEX_DATABASE_URL=postgresql://relex_dev@127.0.0.1:15432/postgres RELEX_QDRANT_URL=http://127.0.0.1:16333 PYTHONPATH=backend .venv-c/bin/python scripts/evidence/repair_review_live.py
RELEX_DATABASE_URL=postgresql://relex_dev@127.0.0.1:15432/postgres RELEX_QDRANT_URL=http://127.0.0.1:16333 PYTHONPATH=backend .venv-c/bin/python scripts/evidence/repair_regressions_live.py
```

Both exited **0**. The first script is a one-time retained-state recovery probe, intentionally asserting the original broken states before repair. Do not rerun it against already repaired fixture states expecting the original failures. Safe observations are `artifacts/evidence/repair_review_0919/repair.json` and `regressions-final.json`; prior focused regression evidence remains in `regressions.json`.

| Requirement / accepted finding | Actual observed result |
|---|---|
| R-A2 unknown ownership identity | Schema `a_repair_unknown_0919`, upload `95d4100c-6553-40e8-bf62-3b4359a91978`: failed privacy quarantine, coherent failed document state, **zero provider calls** before association; same upload retried and published after ordinary association with opaque source attribution |
| R-A4 retained leaked original alias | Original review schema `review_privacy_0919`, record `1b752043-38bf-4f10-9702-66b87002b82b`: ordinary new association and erasure job `73bcd920-fa2b-49ac-a036-31ac19f4aafb` removed the original name throughout persisted project data, retained the decision with deleted attribution, removed real obsolete point `ffcfc4de-e37a-56c4-82da-026391626ce0`, and verified real replacement point `9c29728d-ed88-5333-97f1-d31c53a2f977` |
| R-A2/R-A3 retained unrelated upload | Original schema `review_jobs_0919`, stranded upload `1540a08c-2aef-4a0d-8d8d-716e355fa68a`: fresh authorized replacement `e3c57148-dd84-4f87-9de4-ff2f8d0a721f` completed, document processing state completed, real current index verified |
| R-A4/R-C4 retained failed erasure | Original schema `c_live_c_late2`, original job `8f71c03e-2efa-44ef-9d38-c92d8236af53`: actual Uvicorn HTTP PID 80119 / port 47979, original configured admin login; GET retryable, authenticated POST retry **200**; **same durable inventory**, barrier retained through execution, completed HTTP state only after real cleanup; all obsolete points absent |
| R-A2/R-A3/CT-17 direct race regression | Schema `a_repair_race2_0919`, upload `fcb089ab-f340-4990-8fff-96a19c544fdf`: real upsert paused while another source deactivated; no replacement while old write unresolved; late result accepted, old capability rejected with lease_lost; obsolete point removed and replacement `e79e8a78-665f-442a-9f6f-95240c13155e` published. Injected failure after replacement index acknowledgement, before SQL publication; retry completed with **zero repeated delete calls** |
| R-A4/CT-15 touched privacy regression | Same schema, erase `44d7077b-17ed-47cd-b346-079f469e89c1`: selected attribution replaced, other same-name person's opaque attribution and both operational facts retained; unrelated descriptors unchanged and actual unrelated vector verified |

The independent review schemas did not retain account passwords. Their recovery probe explicitly bootstrapped a new synthetic admin membership; it did **not** edit the affected source, jobs or index before invoking ordinary service actions. The c_late2 check used the original private fixture credentials without changing accounts, jobs or input. Its owned HTTP process was stopped after verification. All schemas/collections and safe artifacts are retained for review; no host service or other user's data was modified.

Supplemental compilation and `git diff --check` passed. No broad suite, contract-test substitutes, fake provider response, fake embedding or fake successful index acknowledgement was used. This report addresses the finite accepted findings and touched races; final acceptance still requires the parent’s independent re-review. Rules-based name candidates deliberately fail closed on uncertainty; optional external detector coverage, provider/backups retention and deferred visualization are unchanged limits.
