# Slice A evidence

Status: implementation-ready; real verification completing, 2026-09-19.
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
| R-A2 source-format/privacy matrix; R-A1 all canonical read entry points | Dedicated source live driver still executing; pending until final observations |
| R-S / R-G4 | Isolated resources implemented; coordinator simultaneous real run pending |

## Failed attempts and repairs

Initial a1 failed provider availability because empty role-specific keys missed the already configured OPENAI key fallback; runner corrected.
advanced1 used too-short test leases for actual generation; corrected to15s.
advanced2 passed restart and same-name erasure, then exposed invalid model month-only dates; B now preserves unknown precision and safely rejects malformed outputs.
Late-write execution exposed inventory rolling back when a writer remained unresolved; inventory/draining now commit separately before external outcome checks.
C's browser found deactivation document metadata stayed pending; fixed and C verified two fresh real browser lifecycle runs.
source1 exposed false quarantine of normalized From headers; fixed. source2 exposed a test assumption about JSONB object order; source assertions now use canonical source line ordinals, and record list sorting uses explicit creation time/id.

The live runner now invokes advanced/source drivers itself; no contract-test or canned provider response marks a live requirement passed. Optional external privacy-detector execution is not claimed. Backups, external provider retention, unmanaged corpus and downloaded content remain explicit limits.
