# Independent compliance review — revision 3

Status: FAIL — finite repair handoff; live acceptance remains incomplete.
Date: 2026-09-19.
Contract: docs/implementation/compliance-repair-spec.md, frozen revision 3, read completely.
Baseline/observed HEAD: 7034c7591b3b8f2e7dccdf3a10d283790121abdd.
Original implementation comparison: 2063eba9b3f9619653a5b1640b2e87ce725b1c4d.

This recovery review replaces the interrupted review, not its unsupported conclusions. Original comparison is almost entirely newly introduced application code. No committed product repair exists after the pinned repair baseline. Inherited docs/quickstart.md changes and untracked scripts/product/start.sh were preserved. All 25 pinned-input hashes were checked: 24 match; quickstart alone differs, as already disclosed by the coordinator. Only this report was edited. No full suite, worker runner, browser replay, data mutation, restart or deletion was performed.

## Finite prioritized findings

### F1 — P1: production has no mandatory semantic privacy agent
Requirements: R2/R3/R9; PRIV-01–05/08/09. Source: Pseudo-AI-agent.md identification engine, contextual circumstances, personal OP_ID and singling-out sections; ai-agent-architecture.md:71–90; frozen repair authority explicitly supersedes optional-model language.

backend/app/bootstrap.py:40–46 constructs EvidencePlatform without a detector. evidence/service.py:32–35 defaults it to None. jobs.py:202–219 only invokes an optional detector, separately for each line; its types represent names/contacts/private discussion, not a complete typed source-bound privacy plan. Even if injected, jobs.py:238–245 sends output through the same blanket regex veto. privacy.py:46–63 mistakes capitalized organizations and metadata for unresolved people. No semantic classification of personal IDs or singling-out roles exists. Merely plugging a model into the existing optional interface does not satisfy the approved contract.

Independent execution of actual normalize() reproduced ambiguous=True for Acme Org, Service Delivery, Phase: Implementation and Decision: October rollout approved. Conversely OP_ID 447102 processed the write-off. returns ambiguous=False. The latter demonstrates a candidate blind spot; final privacy correctness requires a real contextual model, not a new regex exception list.

Repair: mandatory complete-record/bounded-batch privacy model, typed coverage/entities/evidence links/edit operations, exact source-version/Unicode-range validation, context-preserving deterministic application and one bounded correction pass. Distinguish organizations/roles/personal IDs/contextual causes without inventing dates or broadly generalizing operational facts. No model-outage fallback. Exercise all PRIV-09 cases with real model calls before declaring verified.

### F2 — P1: identity resolution and privacy recovery are not durable or actionable
Requirements: R4/R8; PRIV-02/03/06/07/08.

jobs.py:201 stores detector results only in the local detected dictionary; jobs.py:243 overwrites text without persisted original-to-sanitized edit maps, model/prompt provenance or batch coverage. The saved maintenance ArtifactBatch is later and is not a privacy checkpoint. jobs.py:239–240 treats any detected new name absent from the preloaded registry as uncertain instead of supporting source-evidenced fresh identities. jobs.py:248–250 exposes only privacy_unresolved. main.py:215–229 offers person association and retry but no source-occurrence diagnostic/resolution endpoints; frontend/src/app.ts:168–172 likewise has only a generic association form. service.py:308–317 replaces a person mapping with no privacy-plan invalidation/provenance.

Repair: restricted persisted privacy runs/batches/edit maps/occurrences and evidence-backed identity proposals. Add admin-only location/reason/resolution workflow tied to source version; validate resolutions, reprocess affected plan and retry the same job. Identity/policy/source changes invalidate checkpoints. Keep same-name entities distinct. Include these new stores, aliases and diagnostics in erasure and restart inventory. Test crash after completed privacy output, restart reuse, stale binding rejection and erased-plan nonresurrection.

### F3 — P1: relational authority and restricted mapping separation are absent
Requirements: R6; PRIV-06/07. Sources: database.md:38–168; ai-agent-architecture.md:38–65; worker A A1; frozen R6 migration rules.

backend/migrations/001_evidence.sql:1–18 defines only users, sessions, projects and schema_migrations. Live manual_demo has exactly these four tables. evidence/service.py:28–29 puts memberships, documents, records, people, jobs, artifacts, dependencies, conversations, messages, answers and operations into one project JSON graph. service.py:115–133 reads/writes that entire graph through a common connection; jobs.py:75–98 does the same. Raw mappings and raw source are colocated with canonical evidence (jobs.py:228; service.py:316); there is no separate restricted table/privilege boundary. Public DTO filtering exists, so this is not a claim that the public API already dumps raw mappings.

Required table/backfill map: users and sessions remain; projects retain IDs/name/generations; memberships link project/user/role/access revision; documents link project and processing state; records, versions and spans link source/version/location; jobs/leases and index-operation ledger retain stage/token/outcome/IDs; restricted identities, aliases, occurrences, privacy runs/plans/resolutions retain scoped lineage; memories/chunks/history/dependencies/rebuild plans retain source references; conversations/messages/answers/receipts/answer dependencies retain ownership and eligibility. Add explicit project/version/ownership constraints. JSONB is appropriate within metadata/prose/plans, not as the sole graph authority.

Organizations/global role/custom-role UI are approved scope differences, not reasons to invent new privileges. Structured decision ledger is optional; Qdrant replaces DBML vectors; opaque identities replace name columns; safe operation/count audit replaces purged_name. Keep these deviations explicit.

Repair uses additive migrations, isolated restore/backfill rehearsal, consistent paused cutover, one new authority, preserved user IDs/accounts/sessions/jobs/source IDs, restricted recoverable legacy material and erasure tombstones on restoration. No DROP/CASCADE authorization. No assertion that post-cutover rollback is safe without reverse synchronization. Record actual encryption/key-management facilities rather than claiming a vault/HSM deployment.

### F4 — P1: parsing fabricates semantic locations and misses corpus message boundaries
Requirements: R3/R5/R7/R9; PRIV-01/03/04. Sources: ai-agent-architecture.md:54–73, receipts section; worker A A2; production-behavior.md:67–97.

evidence/parsing.py:10–19 splits only certain English From: layouts with narrow delimiter/Date/Subject assumptions. Lines 23–34 recognize limited dates. Line 38 assigns every physical line its own paragraph and transcript turn, including disclaimers/blank lines/metadata, and always sets timestamp_label=None. No explicit speaker/quoted-history structure is persisted. Exact duplicate whole-record hashes exist (jobs.py:227), but do not identify duplicated quoted messages.

Actual corpus probe: transcripts/15_2025-09-12_fresh-phase2-escalation.txt has 669 physical lines and is assigned 669 turns; the synthetic disclaimer is labeled turn 1. emails/16_dc2-hypercare-incidents.txt declares five messages and contains Swedish Från/Skickat/Till/Kopia/Ämne headers; parser produces one record. This is a source-boundary defect, not a model quota issue.

Repair structural email/transcript/report parser with source coverage and actual turns/timestamps, multilingual/irregular headers present in corpus, message/quote provenance and duplicate lineage. Preserve uncertain date/timezone semantics instead of inventing precision. Do not split every embedded From line into independent corroboration. Validate all 45 inputs and imported boundaries before semantic/citation acceptance.

### F5 — P2: aggregate maintenance rereads the entire project under one answer budget
Requirements: R7/R9; worker B B1; ai-agent-architecture.md:124–142 (affected-topic/local recomputation).

jobs.py:173–177 creates an aggregate plan containing every published active record after each base publication. intelligence/maintenance.py:173–189 reads all those records into a single ToolSession using answer limits and sends all sources for topic generation. Old-topic reuse at :203 occurs only after the global read/model call, and uses dependency equality rather than avoiding global recomputation. bootstrap.py:49–51 defaults the phase to 24 tools/pages and 24,000 code points. A project with more than 24 one-page records cannot build this overview through that path: it fails before model generation. The 45-file corpus exceeds the simple one-page lower bound once published, even before correctly splitting email messages. This independently contradicts incremental maintenance, not just a hypothetical scaling optimization.

Repair create affected-topic plans with retained dependency closures; build/update bounded topic summaries and overview from eligible summaries without rereading all source records in one answer session. Keep public overview grounding against canonical evidence and explicitly report incomplete coverage. Verify unrelated addition preserves unaffected topic versions/hash, and actual full corpus overview remains usable without dropping records or raising unbounded limits.

## Requirement and source traceability matrix

Code-inspected means implementation exists but is not a renewed live PASS. Historical worker reports are historical evidence only. This matrix groups coherent substantive clauses; final repair evidence must name scenario outcomes, not treat grouped coverage as blanket acceptance.

| Contract | Source clauses / slice requirements | Current mapping and disposition |
|---|---|---|
| R1 | All rows below; source-authority hierarchy; A1–A4/B1–B4/C1–C4 | This finite map establishes review traceability, not whole-product compliance. F1–F5 confirmed; residual live cases below explicitly unverified. |
| R2 | Architecture §3; Pseudo identification/context engine | F1/F2: absent mandatory model, typed coverage and durable privacy stage. |
| R3 | Architecture §2/3; A2 identity/privacy; production §4.4 | F1/F2/F4: organization/header false positives, personal-ID blind spot, no semantic edit mapping. Existing known-alias normalization is insufficient. |
| R4 | A1/A2/A4; user-features admin; Pseudo separation | F2/F3. Admin-only people API exists; no occurrence-resolution workflow or restricted persisted privacy boundary. |
| R5 | Architecture §3.1; A2 parser/duplicates/source provenance | F4. Physical source line text survives, but semantic turns/message dates/quoted history are not represented correctly. |
| R6 | DBML domain tables; architecture §2; A1 canonical concepts | F3 with explicit table/backfill map above. Current live table list confirmed. |
| R7 | Production §4.1–4.3; architecture §4–9; B1–B4 | Maintenance L1/L2 plus chunk embedding exists (maintenance.py:69–129); F5 aggregate defect. Hybrid candidate validation/record expansion exists (retrieval.py:33–83; tools.py:95–119). Separate reviewer/tools and bounded repair exists (answering.py:86–165). Source/effective/learned fields and independent history review exist (maintenance.py:131–164). Exact receipts/digest/release exists (service.py:461–507). Semantic correctness B-C1–9 and full corpus not freshly established. |
| R8 | Production §3.1/3.2/4.4; architecture §10/11; A1/A3/A4; C1/C3/C4 | Session/member/access revision rechecks service.py:115–131; owner-scoped attempts/messages/answers :391–522; actual chat routes main.py:185–198. Jobs leases, barrier/inventory/draining/late index ticket logic jobs.py:24–118,256–371. Actual controls exist; new privacy/storage repairs must preserve them and extend inventory. No new lifecycle defect claimed solely from missing live retest. |
| R9 | Corpus P1–P9; PRIV-09; real-service policy | 45 original .txt files independently counted. Historical corpus report: 45 parsed, 45 failed privacy_unresolved, zero published; no nine-question or nonempty erasure acceptance. F1–F5 prevent completion. Must execute corpus questions through product, opaque-identity admin oracle, then P7 and P1 replay. |
| R10 | C1/G1–G4; quickstart; actual-service policy | API18080 and Qdrant16333 health successful; PostgreSQL15432 queried. Historical runners/ports exist. No restart/browser/manual end-to-end acceptance rerun here. Generation transport fails current JSON contract; embeddings succeed (1024 dimensions). Final PASS blocked pending repaired runtime/evidence. |
| PRIV-01 | Complete records/context/no regex trigger | F1/F4. Optional line detector and incomplete structure. |
| PRIV-02 | Typed model output/evidence/co-reference/coverage | F1/F2. Current Detection DTO is insufficient. |
| PRIV-03 | Validated deterministic edits/new identities | F1/F2/F4. No coverage/edit-plan persistence; registry-only name check. |
| PRIV-04 | Private-cause masking/facts/exact mapping | F1/F2. PRIVATE regex removes a small phrase set; no model context/edit-map proof. November must remain November. |
| PRIV-05 | Personal identifiers/singling-out risk | F1. Actual no-regex-hit OP_ID probe not quarantined; no contextual risk channel. |
| PRIV-06 | Restricted mapping/service privileges/truthful encryption | F3. Single graph/common DB connection; no isolated table privilege configuration demonstrated. |
| PRIV-07 | Durable privacy checkpoints/invalidation/erasure | F2/F3. Existing later maintenance checkpoints cannot substitute. |
| PRIV-08 | Bounded correction/no unsafe fallback/visible failure | F1/F2. Model not in mandatory path; generic quarantine only. |
| PRIV-09 | Actual corpus model execution/restart/outage/erasure | R9 BLOCKED; no privacy model adapter exists to execute. |

## Additional source coverage and approved differences

- Production §§3/4 evidence and citation UX: main.py:159–203; frontend/src/app.ts:105–155 provides source version/precise span view, hover/focus/tap popover and new-tab links. API release precedes serialization; no factual streaming path. Browser usability not replayed here.
- Architecture §5/6 and B2 tools: scoped hybrid search, canonical SQL eligibility, pagination, chunk coverage and finite budgets exist. Search and answer use same retrieval service. No raw SQL/deletion tool is exposed to the agent. Exact filters/current-state claims require fresh live evidence after repair.
- Architecture §7/8, B3/B4: separate reviewer context and counterevidence searches exist; source times and review state persist. B-C1 proposal/commitment, C2 effective time, C3 never-true, C4 out-of-order, C5 missing facts, C6 conflict, C7 distinct scopes, C8 forwarding/duplicates, C9 incomplete history are all semantic acceptance scenarios, currently unverified by this review; F4 directly compromises C8.
- Architecture §10 and A4: controlled cleanup currently removes raw uploads, identity mappings and affected sources/artifacts, empties saved answers and drains known old index operations. Changes must preserve same-name isolation, failed cleanup retry and late-writer fencing. Full source/provider/backup inventory remains required; this review did not claim erasure complete.
- UI §§1/2/4–7/10 and C1–C4: document/search/chat/status/admin paths exist; registration and email grants are later authorized extensions. CSRF/session/role controls and no-store are in main.py; source/model text uses DOM textContent helpers. Project-local roles/opaque people are intentional. Global admin bypass, organization management/custom-role designer, general non-project chat, cross-project association management, organization-wide erasure, PDF/OCR and visualization are approved exclusions, not repair demands.
- database.md decision prose/structured ledger, pgvector and purged-name audit are explicitly reconciled deviations; wholesale project JSON authority is not.
- Pseudo background header versus newer user requirement: newer mandatory model instruction wins. HSM/KMS deployment, DPO role, broad quasi-generalization, invented mid-November precision, mapping-only erasure and anonymity/GDPR guarantees are not adopted. Do not reproduce them to claim literal compliance.
- CT01–08 and CT11–16 correspond to retained auth/release/source/overview/provider/ownership/barrier code above; no fresh real probes of these races were run. CT09/10 late writes and CT17 durable maintenance checkpoint paths remain in jobs.py/maintenance.py, but privacy checkpoints are missing and are a separate new required stage. Independent runner isolation and simultaneous G4 are historical results; do not rerun unrelated full suites for this review.

## Independent observations and verification limits

Read-only probes used the installed Conda Python and actual code/services, not mocked services or worker-authored runners. No secrets or raw private mappings were printed.

1. GET http://127.0.0.1:18080/health -> 200, database ready/index ready/model configured_unverified. Qdrant http://127.0.0.1:16333/healthz -> 200.
2. PostgreSQL at 127.0.0.1:15432, database postgres, queried pg_tables for manual_demo -> projects, schema_migrations, sessions, users.
3. Actual preprocessing/parser observations recorded under F1/F4. These code probes establish the narrow deterministic defects, not complete model/product acceptance.
4. Existing configured generation endpoint returned HTTP200 with a non-JSON response to a tiny synthetic availability request. One invocation through actual ModelProvider.generate also raised ProviderFailure(provider_unavailable). The actual embedding adapter succeeded with dimension1024. This review did NOT reproduce the previous429 quota error, and therefore does not claim quota is still the cause. Do not increase budgets/accounts or repeatedly retry; inspect authorized generation protocol/configuration during implementation. No privacy raw corpus was sent to a new endpoint.
5. No actual privacy stage exists; generation/reviewer end-to-end success is unverified. No browser, corpus ingestion replay, migration, restart, lifecycle or erasure execution was performed in this bounded review. Historical PASS records do not certify frozen repair revision3.

## Repair handoff and stopping rule

Accept F1–F5 as the finite repair scope under the frozen contract. F1/F2/F3 are coupled substantial work; keep one implementation worker. F4 is structural evidence repair and F5 is required incremental maintenance, not a general refactor. Worker must preserve inherited user files and accounts, use restricted backup/clone cutover procedure, and run actual product paths. Provider compatibility must be diagnosed without assuming the old quota failure. Only actual successful generation/privacy/reviewer/embedding/browser/corpus/erasure evidence can close the corresponding acceptance gates.

Re-review only these findings, touched requirements and concrete regressions. No overall PASS until R1–R10/PRIV01–09 required evidence exists. Unknowns above are verification obligations rather than invented defects or permission for unbounded audit.
