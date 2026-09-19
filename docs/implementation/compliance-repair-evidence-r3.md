# Compliance repair evidence - revision 3

## Focused re-review repair after `305b549`

Status remains **PARTIAL / BLOCKED**, not PASS. The frozen revision 3 semantics are unchanged.

- R2/R3/R9, PRIV-01/03/05/09: protected `person`, `contact`, and `personal_identifier`
  entities now require an exact source-bound edit, except an uncertain quarantined entity or the
  explicit `system_code` non-edit classification. A final deterministic scan verifies edit mapping
  and rejects surviving email, phone, or OP_ID values before `privacy_ready`.
- R4/R8, PRIV-02/03/07/08: admin resolutions persist and revalidate diagnostic ID, record/version,
  source hash, span ID, Unicode range, exact source text, kind, reason, decision, and administrator.
  Bind and non-bind decisions have kind-specific contracts and must be applied by the retry model output.
- R4/R6/R8, PRIV-06/07: ordinary PostgreSQL connections set only `<schema>,public`; restricted
  privacy/admin/worker operations explicitly request `<schema>_restricted`. A separately provisioned
  `RELEX_RESTRICTED_DATABASE_URL` is supported. The configured deployment still supplies only the owner
  URL, so separate runtime-role enforcement remains BLOCKED pending safe credential provisioning.
- R6: migration 004 adds typed scoped ownership/reference columns and FKs for conversations, messages,
  attempts, answers, receipts, checkpoints, job-document/version links, and polymorphic dependency owners.
  `record_dependencies` is populated from answers, memories, staged artifacts, receipts, and rebuild plans.
  Two legacy job payloads reference already-deleted documents; their audit payloads remain preserved while
  no typed live-reference row is created for the absent target.

Focused evidence:

1. `pytest -q backend/tests/evidence/test_compliance_repair.py backend/tests/product/test_transport.py`
   reports 6 passed, including the contact-entity/zero-edits regression and the single correction bound.
2. Restoring `manual_demo-quiescent.dump` into isolated `repair_r3_focus_305b`, then running migration 004
   twice, yields versions `1,2,3,4`, 14 jobs, 12 valid job-document links, 12 valid job-version links,
   and preserves the two stale historical document IDs only inside job audit JSON.
3. Direct SQL probes reject both a cross-project dependency and a missing record version via foreign keys.
4. A temporary ordinary role can read `manual_demo.projects` and receives `permission denied for schema
   manual_demo_restricted`; the role is transaction-local and absent afterward.
5. The isolated service probe persists an exact source-bound bind decision, retries the same job ID,
   invokes the model with that resolution, sanitizes `Alice Example`, and reaches `privacy_ready`.
6. An isolated ordinary-path service mutation persists typed conversation ownership and message linkage.

Known provider and Chromium blockers below remain unchanged. No host-wide dependency or provider change was attempted.

Status: IMPLEMENTED with partial LIVE-VERIFIED evidence; external-model and browser gates remain BLOCKED.
Contract: `docs/implementation/compliance-repair-spec.md`, frozen revision 3.
Baseline: `7034c7591b3b8f2e7dccdf3a10d283790121abdd`.
Repair start HEAD: `b96e6664def919b3d9587617440d31f8b664dc2e`.
Date: 2026-09-19.

This report covers only accepted F1-F4 work. Concurrent intelligence/progressive-context edits and inherited documentation/start-script changes are outside this repair and were not staged. No overall PASS is claimed.

## Requirement map

| Finding / requirement | Implementation | Evidence and disposition |
|---|---|---|
| F1; R2/R3/R8/R9; PRIV-01..05/08/09 | Mandatory record-level privacy agent runs on every parsed record, including clean input. Ordered bounded batches carry structural overlap, exact source hash, prompt/policy/model versions and complete span coverage. Entity/edit ranges include exact Unicode text. Application validates ranges, evidence, overlap, deterministic email/phone/OP_ID candidates and edit authority. One correction call is allowed; provider or second validation failure blocks publication. Application allocates deterministic project-local opaque IDs only for supported `NEW_*` proposals and quarantines uncertainty/same-name conflicts. | Focused privacy tests PASS. Actual configured safe probe returned `provider_unavailable`; isolated product job failed retryably at `parsed` and had zero published records. Therefore actual 45-file privacy execution and downstream corpus questions remain BLOCKED. |
| F1/F2; R4/R8; PRIV-06/07 | Complete validated plans, batch hashes, coverage, exact edit maps, identity revision and occurrences persist in restricted tables before `privacy_ready`. Plan reuse requires matching source/policy/prompt/model/identity revision. Admin diagnostics expose record/version/span/range/reason; constrained resolution invalidates the plan and privacy generation, and existing retry runs the same job. Erasure removes affected plans/diagnostics/resolutions and nulls deleted identity links while recording a tombstone. | Isolated clean-record flow: one provider call, stage `privacy_ready`, one persisted run/plan, record not quarantined. Empty-identity plumbing probe: identity row 0, tombstone 1, barrier false, job completed. This is not claimed as nonempty corpus erasure acceptance. |
| F2/F3; R6/R8; PRIV-06/07 | Additive migrations create memberships, project state, documents, records/versions/spans, jobs/index ledger, named artifact/conversation tables, restricted raw/identity/privacy tables, and erasure tombstones with FKs. Runtime HTTP and worker transactions reconstruct from normalized rows and update them transactionally. `projects.data` is reduced to a non-content migration marker. Restricted schema is excluded from public grants; the configured owner credential retains access and no separate KMS/HSM or encryption-at-rest claim is made. | Backup restored into `repair_r3_restore`, migrated to versions 1/2/3, and preserved 9 users, 22 sessions, 3 projects, 4 memberships, 12 documents, 12 records, 14 jobs and all IDs. Worker parse mutation and API read both observed `parsed` with one record. Live `manual_demo` cutover completed quiescently with 3 legacy markers and zero invalid record references. |
| F3; R6/R8 | Quiescent cutover used two mode-0600 schema dumps. Normalized authority was verified before legacy JSON was scrubbed. Recovery material remains outside the served schema. | Pre-cutover SHA-256 `2914c442905b3777049b944ad0e51190f56f996bdd0bc41dc4313a918959118b`; quiescent SHA-256 `2b5ebb7ec17369ee3b88a6f2ad7f719872aedccc9b86168d54f22b1f639f105c`. Post-cutover health reports database/index ready. |
| F4; R3/R5/R7/R9; PRIV-01/03/04 | Parser supports English, Swedish, German, French and Spanish email header variants, preserves source lines, splits complete header blocks, labels quoted/forwarded provenance, derives real transcript turns/speaker/timestamp labels, and avoids treating disclaimers as turns. Reports retain paragraph boundaries and uncertain source time. | All 45 files reconstructed byte-for-line using `splitlines`; 135 record boundaries produced 135 distinct hashes. The known five-message multilingual email parses as 5 records. The 669-line escalation transcript produces 187 turns; first turn is line 15. Semantic citation correctness remains BLOCKED behind privacy provider. |

## Verification commands and observed results

```text
PYTHONPATH=backend python -m pytest -q backend/tests/evidence/test_compliance_repair.py backend/tests/product/test_transport.py
..... [100%] - 5 passed

PYTHONPATH=backend python -m compileall -q backend/app
PASS

git diff --check
PASS

GET http://127.0.0.1:18080/health
{"database":"ready","index":"ready","model":"configured_unverified"}
```

Additional isolated probes observed:

- migrations: versions `1,2,3`; 25 ordinary and 10 restricted tables after the metadata occurrence split;
- relational consistency: API document `running`, `jobs.payload` stage `parsed`, reconstructed graph stage `parsed`, records `1`;
- actual privacy dependency: `privacy_actual_blocked provider_unavailable`;
- actual safe outage path: job `failed`, stage `parsed`, error `provider_unavailable`, retryable `true`, published `false`;
- frontend: `npm run build` PASS;
- browser: BLOCKED because the installed Playwright package has no Chromium executable. No browser package download was authorized.

## Backup and restoration limit

Backups are stored under `artifacts/compliance/r3-backup/` with mode 0600. They contain pre-erasure legacy personal data and are restricted recovery material, not active authority. A restoration must occur into an isolated schema, run migrations, reapply every `erasure_tombstones` identity to the restored normalized/restricted data, validate counts and references, and only then permit serving. The repair does not claim tested post-cutover rollback safety; fix-forward is required after new writes. The clone rehearsal proves pre-cutover restore/backfill only.

## Blockers and residual risk

1. The configured model endpoint returns `provider_unavailable` for the safe privacy probe. Per the frozen contract, no fallback was used and no further corpus/provider attempts were made. PRIV-09, corpus P1-P9, generation/reviewer paths, nonempty Kwame erasure and post-erasure P1 remain BLOCKED.
2. Chromium is absent from the installed Playwright cache, so new browser acceptance is BLOCKED. HTTP health and frontend compilation are supplemental, not browser acceptance.
3. The inherited `scripts/product/start.sh` preflight intermittently reports `18080` in use during immediate socket teardown despite no listener. The owned API/worker were restarted directly with the same saved environment. Repeatable launcher acceptance remains BLOCKED.
4. Restricted PostgreSQL objects revoke `PUBLIC`; the current deployment uses one database-owner credential for ordinary and restricted application paths. Application APIs/tools enforce the boundary, but a separately provisioned least-privilege database credential is not configured. No stronger DB privilege, encryption-at-rest, KMS or HSM property is claimed.
5. The full F4 semantic/receipt outcome cannot be established until model-backed publication succeeds. Structural losslessness and provenance metadata are verified; question correctness is not.
