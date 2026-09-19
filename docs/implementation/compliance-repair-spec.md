# Spec and documentation compliance review and repair

Status: frozen
Revision: 3
Baseline: 7034c7591b3b8f2e7dccdf3a10d283790121abdd
Original implementation comparison: 2063eba9b3f9619653a5b1640b2e87ce725b1c4d
Repository: verda:/mnt/relex-kai
Objective: independently review the delivered product against its source requirements, expose implementation-spec drift, repair confirmed in-scope defects, and verify the repaired product using the actual Acme corpus and real services.

## Revision history
- Revision 3: Explicitly confirmed by the user with 'confirm'; frozen for independent review and bounded repair.
- Revision 3: Second self-review resolved requirement-ID collision, source/version edit semantics, initial/retry/erasure model coverage, identity rendering, live migration consistency, restricted-data retention and provider-blocked acceptance. Awaiting confirmation.
- Revision 2: Self-review against Pseudo-AI-agent.md and explicit user correction: the model is central, not optional assistance. Added model-led privacy stages, evidence-bound transformations, contextual identifiers, isolated mapping storage and restart acceptance. Awaiting confirmation.
- Revision 1: Initial review/repair contract. Awaiting explicit confirmation before agent dispatch or implementation.

## Authority and reconciliation
Use current user instructions first. Production behavior and ai-agent-architecture define required behavioral/architectural outcomes. Compare user-features, user_ui and database DBML explicitly; record every significant difference rather than silently declaring source compliance.
The earlier confirmed delivery revision4 supplies previously accepted scope decisions: project admin/member; project-grounded chat; project-local erasure; UTF-8 input; deferred visualization; Qdrant vectors; opaque identities; no raw purged-name audit. Registration and email-based access grants are later user-authorized additions and must remain.
Those decisions do not authorize abandoning model-led semantic privacy processing, lossless semantic source boundaries, or replacing the canonical relational domain structure wholesale with a project JSON blob.
The user's current correction overrides the notes' reference-only label and earlier optional-model wording for the central role of the privacy model. Adopt the notes' semantic identification, consistent tokenization, restricted mapping separation, contextual-private-cause masking, and detection of singling-out descriptions. Do not infer that this adopts every example, infrastructure prescription or legal assertion. Broad quasi-identifier generalization/HSM and mapping-only erasure remain outside this delivery; flag contextual risks without automatically deleting operational roles, dates or locations. No anonymity guarantee.
Original specification documents are historical inputs; do not rewrite them to make deficient code appear compliant. Corrections belong in a separately versioned current contract and traceability report.

## Required outcomes
| ID | Required outcome | Evidence |
|---|---|---|
| R1 | Whole-delivery traceability: every substantive requirement in source docs and A/B/C specs mapped to current code and evidence, approved deviation, confirmed defect, contradiction, or unverified behavior | Independent finite matrix with source clause/line, code location and rationale; no blanket PASS |
| R2 | A mandatory model-led privacy agent processes every newly imported or externally edited source record before downstream generation/embedding; valid persisted plans may be reused as specified below. It classifies entities and contextual privacy risks, proposes source-bound identity links and transformations. Regex/NER supplies candidates and deterministic validation, not the semantic authority or a fallback pipeline | Real privacy-model calls for all record batches including inputs with no regex hit; no publication without a completed validated privacy result; outage is a visible retryable dependency failure |
| R3 | Context-aware preprocessing distinguishes people, organizations, roles, metadata and contacts; preserves offsets/facts; uncertain identities remain quarantined | Real corpus plus unknown-owner, Unicode, multi-recipient and same-name cases; no source alterations or corpus-specific bypass |
| R4 | Project-scoped identities/aliases and admin-only actionable resolution diagnostics; no automatic same-name merge or unexplained permanent quarantine | Actual admin API/browser resolution and same-job retry; raw values excluded from ordinary logs/member UI; resolution data included in erasure |
| R5 | Email/report/transcript parsing preserves appropriate boundaries, chronology, speaker/quote provenance and all content | Inspect actual45-document corpus canonical spans and record boundaries; quoted forwarding must not become invented independent corroboration |
| R6 | Reconcile core storage with documented relational concepts: users, projects, memberships, documents, records/versions/spans, jobs, identities/occurrences, artifacts/dependencies, conversations/messages/answers/receipts | Independent DBML-to-actual map, additive migrations/backfill, IDs/ownership/references preserved, real PostgreSQL constraints/restart checks. JSONB remains for prose/metadata, not the entire authoritative project graph |
| R7 | Preserve and repair maintenance, bounded retrieval, independent grounding review, chronology, precise receipts and release gating wherever confirmed violations occur | Changed paths reviewed against original source clauses; actual generation/reviewer/embedding/Qdrant evidence and source-linked answers |
| R8 | Preserve project/owner isolation, registration/admin access, durable job recovery, activation/deletion, erasure inventory and late-writer fencing | Focused actual HTTP/browser/database/index probes on touched boundaries and original retained failure cases |
| R9 | Corpus acceptance and truthful limits | All45 originals accounted for; every remaining quarantine justified individually; practice P1–P6/P8–P9 with citations, P7 erase Kwame then P1 again; no fabricated missing answers or zero-data erasure PASS |
| R10 | Repeatable usable delivery | Verified migration/startup/run instructions, running owned services, report observed ports/PIDs, final independent PASS only when required evidence exists |

R6 explicitly proposes relational reconciliation in this new revision; approval of this revision authorizes its implementation, not deletion of existing application or verification databases. Build and validate on isolated clones first. Keep old data recoverable; no irreversible DROP/CASCADE or broad cleanup.

## Review boundaries and categories
Required: R1–R10 and PRIV-01–PRIV-09 including source-vs-plan drift. Existing defects introduced by the original delivery remain in review even if committed before this repair baseline.
Direct regressions: changes break current accounts, grants, project access, source IDs, receipt/version eligibility, privacy, durable recovery or safe failed-provider behavior.
Out of scope: global admin/custom-role product expansion, general chat, new visualization design, PDF/OCR, organization-wide erasure, HSM/k-anonymity, unrelated cosmetic refactoring and deletion of old verification schemas.
Database organizations/role-design differences must be reported; do not invent global access powers or an organization management UI to satisfy a literal old DBML sketch. Any unresolved material contradiction returns to the parent for an explicit spec revision.

## Model-led privacy contract (revision 3)

This section supersedes the earlier optional detector semantics for this repair. The model is central to semantic interpretation; the application retains authority over authorization, identity allocation, persisted transformations and publication.

- PRIV-01 Context and coverage: model input is a complete record or ordered bounded batches with structural context and continuation. Parse headers/turns without losing source text. Track every covered span, including names/OP_ID references, organizations, roles, metadata, signatures, shortened references and contextual private circumstances. No regex trigger is needed to invoke the model. A model's clean result must still pass deterministic contact/coverage checks.
- PRIV-02 Typed model result: source span IDs and Unicode ranges; entity type (person, organization, role, contact, personal identifier, contextual circumstance, uncertain); supported co-reference/alias links; proposed replacement/removal operations; unresolved reasons; coverage. Identity proposals must reference evidence, not arbitrary new factual associations. Organization/role classification comes from context rather than capitalized-word quarantine.
- PRIV-03 Controlled transformations: application validates offsets, overlap, full batch coverage and references; allocates project-local opaque IDs; applies a deterministic edit plan. Explicitly evidenced new identities may be proposed/created without requiring a complete preloaded roster; conflicts and same-name ambiguity require restricted admin resolution. Raw model free-form rewrites are not canonical source text.
- PRIV-04 Contextual preservation: remove private cause while preserving only operational constraints explicitly present. For example, 'out until November for surgery' may become '[person] unavailable until November'; it MUST NOT become 'mid-November'. Preserve uncertainty, speaker attribution and original-to-sanitized source mapping. Do not coarsen locations/roles that are necessary evidence merely because a model labels them sensitive.
- PRIV-05 Personal IDs and singling-out: distinguish a personal operator identifier from product/system codes using context. Treat source-linked personal identifiers as restricted aliases; detect unique-role/location/shift combinations and report their risk separately. No claim that names/contact removal alone guarantees anonymity. Broad generalization requires an explicit subsequent scope decision, not silent output edits.
- PRIV-06 Restricted mapping boundary: separate raw identity/alias tables and privacy-run data from ordinary canonical evidence access; enforce database privileges/service boundaries so B and ordinary member tools cannot enumerate mappings. Project-admin resolution is the currently authorized control; do not invent a DPO role or pretend an HSM exists. Use explicitly provisioned restricted access and protect secrets outside source control. Record the actual encryption-at-rest and key-management facilities; do not claim unconfigured encryption or add a new KMS/HSM deployment requirement under this clause.
- PRIV-07 Durable processing: persist validated model output/edit plan, model and prompt version, input/source version hashes and coverage before downstream work. Restart/retry reuses a still-valid completed plan; partial/invalid results cannot count as completed coverage. Identity/source/privacy changes invalidate affected plans. Restrict intermediate outputs and include them in erasure inventory; diagnostics must not leak raw payloads.
- PRIV-08 Failure/repair: one bounded schema/semantic correction pass after a rejected privacy output; then visible failure with no unsafe publication. Provider failure cannot route around the model. Deterministic validation can reject unsupported edits; it cannot replace successful semantic classification with blanket name regex quarantine.
- PRIV-09 Acceptance: actual privacy-model execution on all45 corpus files; capture safe coverage metadata and hashes plus restricted input/output inspection. Exercise organizations/metadata, new and known people, conflicting aliases, unknown-owner leak, no-regex-hit identifiers, private medical context with an operational deadline, exact edit-map citations, restart after completed privacy output, provider outage and erasure of the selected person's privacy artifacts. Downstream inputs must contain only validated sanitized source.

## Self-review findings resolved in revision 2
1. R2 understated the requested model role and allowed regex-first semantics to survive behind an optional adapter. Replaced with mandatory record-level model-led processing.
2. R3 lacked a concrete model/output/application boundary and could accept arbitrary model paraphrases. Added typed source-bound edit plans and deterministic validation.
3. The blanket exclusion of the reference's wider privacy scope hid useful required distinctions. Adopted personal-ID/context detection and private-cause masking; explicitly distinguished risk flagging from broad generalization.
4. Identity handling depended too much on pre-registering corpus names. Added supported identity proposals and evidence-backed alias links without same-name guessing.
5. Vault separation and durable privacy-stage recovery were under-specified. Added restricted persistence/access boundary and validated plan recovery.
6. The reference example invents 'mid-November' from 'until November', and its mapping-only deletion conflicts with controlled-store erasure. These are rejected examples, not requirements to reproduce.
7. Reference-only document header and newer user direction conflict. Recorded precedence explicitly instead of claiming the original docs all say the same thing.

## Operational acceptance details

### Unambiguous identifiers and model reuse
PRIV-01–PRIV-09 are privacy requirements. Corpus P1–P9 refer only to PRACTICE-QUESTIONS.md; never use the same IDs for both.
Mandatory model coverage applies to the source content, not every retry attempt. Persisted successful privacy plans can be reused only when source hashes, policy/prompt version, and all relevant identity bindings remain valid. Do not regenerate a completed plan after a crash merely to prove a fresh model call.
Application-controlled erasure may deterministically derive a sanitized version from a validated plan and exact occurrence inventory, without resending deleted raw material to a model. Record the derived version's lineage and revalidate coverage/remaining identities. If semantic reprocessing is necessary, restrict input to still-authorized material and keep the job visibly pending/failed until it succeeds. Never recreate erased mappings during retry, reactivation or migration.

### Exact source mapping and bounded context
Record/spans retain stable identity within a version; every transformation records original and sanitized ranges with Unicode code-point semantics. Model-proposed ranges are validated against the exact version supplied. Changes create new versions and invalidate old receipts according to existing unavailable semantics, not silent quote remapping.
A private-cause edit removes the identified cause without broad prose rewriting; preserving 'out until November' is preferable to inventing an exact date or stronger causal claim.
Batching must cover the complete source record, provide enough overlap/structure for split names and alias references, deduplicate overlap, and checkpoint completed batches. Exhausted context/budgets produce incomplete coverage and block publication. Detection/classification remains model-led; deterministic range/identity checks cannot certify that a model never missed an entity.

### Identity proposals, approvals and rendering
The privacy model may propose a new entity using temporary record-local identifiers. Application allocation is idempotent under the persisted plan; an explicitly evidenced new person can receive a fresh project identity, while cross-record co-reference requires supporting aliases/context. Ambiguous matches stay separate/quarantined. Do not register organizations as people or infer agreement/ownership from identity links.
Admin resolution is a proposed binding/classification, not an unrestricted 'ignore privacy' toggle. Validate it against the same source version, store provenance, and reprocess the affected plan before publication. Restrict non-person exemptions to evidenced context.
Canonical source, retrieval tools, answer/reviewer contexts, index payloads and logs retain opaque identifiers. Preserve the current user-visible policy: ordinary members receive opaque attribution; project admins access mappings only through restricted administration. Corpus attribution checks compare the opaque IDs through an admin-only oracle to the expected people; absence of a human name in ordinary output is not itself a factual failure. After erasure, the selected attribution becomes [deleted user] and cannot be resolved through the oracle.

### Relational migration and one authoritative representation
Before implementation, the reviewer identifies the exact missing relational entities/constraints under R6. The worker records an explicit entity/table/backfill map and migration phases within that approved scope. Preserve externally visible IDs, timestamps, ownership, versions and valid resumable jobs; UUID-looking text IDs need not all change SQL type when that would break existing opaque identifiers.
New relational tables become authoritative; merely mirroring projects.data into unused tables does not satisfy R6. JSONB may retain bounded prose/metadata/edit plans, not an authoritative duplicate project graph.
Validate a backup restore and backfill on an isolated clone. For live cutover, pause owned mutating API/worker operations, drain or reconcile model/index operations and leases, capture the final consistent state, backfill and validate counts/references/access, switch all readers/writers together, then resume. The application must not write both old and new authorities without an explicit consistency protocol. Preserve an observable maintenance state and the existing endpoint on restart.
No irreversible deletion of user data is authorized. Legacy snapshots and migration backups become restricted recovery material rather than active source authority. Inventory their location, access and retention; do not retain unrestricted deleted personal data inside a queryable legacy JSON copy while claiming erasure succeeded. Controlled runtime copies must be scrubbed/inaccessible according to erasure policy. Offline recovery snapshots remain an explicitly disclosed backup limit with a restoration procedure that reapplies erasure tombstones before serving data.
Rollback after new writes is forbidden unless a tested reverse synchronization preserves those writes and erasures. Otherwise fix forward from retained data. A pre-cutover rollback rehearsal on a clone must not be presented as post-cutover rollback safety.

### Corpus and external-dependency gates
Preserve original source hashes and count every imported record/span. Run a fresh isolated corpus project; register only evidence-backed identities/contacts, not a hand-curated exception list that hides detection defects.
Separate results: structural/privacy coverage; successful model-backed publication/indexing; question-by-question semantic/citation correctness; deletion and post-deletion correctness. A justified unresolved case is safe behavior but does not establish corpus-wide answerability. Any quarantine relevant to a question keeps that question BLOCKED, and material excluded evidence must be disclosed.
Prepare expected claims and source locations from corpus inspection in a separate reviewer-only artifact. Do not feed PRACTICE-QUESTIONS answers or evaluation expectations into ingestion. P1–P6/P8–P9 use the pre-erasure project; then run P7 against the exact Kwame identity and rerun P1, verifying retained facts and removed identity across controlled stores. Incomplete evidence must not support a claim that all figures or the current state were found.
All external model calls, including mandatory privacy processing, use explicit authorized configuration. The existing authorized endpoint may serve distinct privacy/generation roles; a separate physical provider or credential is not required. Raw privacy access must be configured deliberately and never inferred from arbitrary endpoints. No provider budget increase or purchase is authorized.
Use IMPLEMENTED, LIVE-VERIFIED and BLOCKED distinctly. Local DB/UI/parser work may proceed during provider outage, but actual privacy classification and downstream corpus acceptance remain BLOCKED. No overall PASS on synthetic substitutions or health checks. Once one safe probe confirms persistent quota failure, stop repeated provider attempts until configuration/state changes.

## Second self-review corrections
- Removed ambiguous privacy P1–P9 IDs that collided with the corpus question IDs.
- Reconciled mandatory model processing with checkpoint reuse and deterministic erasure.
- Specified source-version/range semantics, full-record coverage and cross-batch identity handling.
- Made opaque attribution compatible with corpus 'who' questions through restricted verification.
- Replaced vague encryption instructions with truthful existing-capability reporting and access requirements.
- Specified one relational authority, quiescent live cutover, backup erasure limits and rollback constraints.
- Closed the loophole where justified quarantine could count as complete corpus acceptance.
- Clarified provider isolation, raw-input authorization and the limits of work during quota failure.

## Verification and completion
Use actual PostgreSQL, Qdrant, configured generation/embedding/reviewer/privacy endpoints and Chromium; deterministic probes are development aids, not final acceptance.
Corpus is synthetic and user-authorized for verification. Raw privacy preprocessing must have a separately explicit configuration/boundary, never leak through ordinary B prompts or telemetry. Do not change provider accounts, spend limits or purchase resources.
Recheck provider availability; prior429 project_spend_limit_exceeded is an external blocker, not permission to fake responses. Continue independent local work while affected real-service cases are BLOCKED. No overall completion until required live evidence is available.
Do not rerun full worker suites. Broaden focused probes only when shared schema/privacy changes demonstrably affect related invariants; explain why. Reviewer independently probes critical paths and checks evidence without duplicating worker runners.

## Ownership and workflow
Parent owns this spec and finding classification. Before dispatch every agent reads this entire file and all relevant pinned inputs.
After explicit human confirmation, freeze revision3, then dispatch ONE independent reviewer first (user requested review-first), no descendants. Reviewer compares original implementation diff plus current code against source docs, returns finite prioritized findings and R1 matrix. It does not implement.
Parent validates findings against requirements. Dispatch ONE implementation worker for accepted findings; no descendants, no speculative scope expansion. Worker confirms cwd/status/HEAD, preserves newer user changes, commits explicit owned repair paths progressively. Parent does not duplicate implementation or tests.
Re-review covers accepted findings, touched requirements and concrete repair regressions only. New semantics require a revised spec and explicit confirmation; no moving acceptance goalposts.
Allowed repair scope: backend/app, backend/migrations, backend tests focused on touched requirements, frontend, scripts/evidence/intelligence/product, manifests, .env.example without secrets, new compliance/evidence/setup docs.
Forbidden: editing original corpus, private .env secrets, original frozen source/spec semantics, host services/firewall, unrelated user changes, pushes/deployment, destructive live migration or verification-data deletion.
Take a restricted, restorable schema/data backup before live migration; preserve manual_demo's kai administrator and existing login/session configuration. Apply the cutover and backup rules below. Only restart owned product services as necessary.
Stop with explicit blockers if actual external dependencies cannot be restored within existing authority. PASS requires traceability, repaired findings and actual evidence; current health checks are insufficient.

## Initial confirmed observations (not a substitute for independent review)
- ai-agent-architecture.md §3.3/line88 originally describes model ambiguity assistance; the user's later correction requires a central model-led privacy agent. Implementation worker-A/shared detector wording made assistance optional; bootstrap passes no detector.
- Actual corpus45/45 failed privacy_unresolved.1436/15939 lines flagged with15 identities and0 contacts. Organization/metadata false positives and unresolved aliases are separate causes.
- Earlier bcae74c privacy repair expanded capitalization quarantine to close an unknown-owner leak; corpus representativeness was missing.
- Current migration has users/sessions/projects plus schema_migrations, with almost all canonical state in projects.data. This diverges beyond the documented vector/identity/decision-prose adaptations.
- Earlier PASS applied to narrower evidence and does not establish full source-doc or corpus compliance.

## Pinned inputs and initial state

| Input | SHA256 |
|---|---|
| docs/Pseudo-AI-agent.md | 1350b4b900b78d322597ab9f67a4185ceaa1c7b582eb4e32fd939a5c2c825244 |
| docs/admin-access.md | eb2c06131a090f58b9b92d01b125680f3aea3f730bf835998fd8b925582fddae |
| docs/ai-agent-architecture.md | 78610a73ef68d218b7c4083516ac76273aa042a082850649f7ffdf504a830952 |
| docs/corpus-verification.md | 01df8bb3a480275ea79353db8166e1534ae6861440f4af2e655285bd162424b8 |
| docs/database.md | a0e4907edbb3b9b11b82ac4b863702e034007864de0cb46bd20da3cbb82d048c |
| docs/implementation/README.md | 57d740da9c5abe9bddca308d09674e9726bbeb737f299e725cc5f2494ca1b780 |
| docs/implementation/architecture.md | aad2891cef8831f80fb71bd275b96910e4ffc861136c39afd4348fc5987ac6b7 |
| docs/implementation/delivery-result.md | 9dc00b0b3adb7b3e47ed7c772f3af67768295ab1025feaf90c7d66664f35c942 |
| docs/implementation/delivery-spec.md | 12c1dfb3aa450fd482853d5cadee36e6a73166914f3cdeb148f54ad6bb891b6c |
| docs/implementation/evidence-a.md | 6bb759fdf7f78f34cea40671a885e0906d37709521fafbf7143febe1acb22bc0 |
| docs/implementation/evidence-b.md | 26d9dbaa0432d14481983c7f3b4648f370b37e81f95038bd525829dfb193ee04 |
| docs/implementation/evidence-c.md | 9379cc4daade7ccab0f936cc82d54dbd1c74b8e00b7803b2ad5854fad18f5e68 |
| docs/implementation/http-api.md | a125ad27d4523d6abdd4f39b5a379c19b32dff8b078e202c85a46bffe9429aa2 |
| docs/implementation/independent-testing.md | c8f78ab266beb931c4d6ec306d592af6ea3439379ab8bfc4beebd04b88038115 |
| docs/implementation/real-service-verification.md | f4ce05bacdcee8671e96651b045d74cf1f825ae16d8c3385b9afabcb0c10dc50 |
| docs/implementation/shared-interfaces.md | 3b47a08a67145a8190287cf92d45f904996793fa330791833e57fefb9026f297 |
| docs/implementation/worker-a-evidence-platform.md | 262dcfe3533042cd72459aa31066357238dcbae44dc8ab83292b40be50c9294f |
| docs/implementation/worker-b-intelligence.md | 87f2ae6bbb951c5b88fb0a57aac5e9c4747568d7fee71219c3299b87492af503 |
| docs/implementation/worker-c-product.md | 6a2b0eeed6868589b3d25be566676fe7d17e9063fb502b91321d2fe4c9a020c5 |
| docs/privacy-unresolved-plan.md | b52a00ad7716d59b7dd35a1e068a9c300668acedbb15dfb32d83094f651d333e |
| docs/production-behavior.md | 8dee98c55acd566612dba1a65c096e5401edadc1746d77eca9175303191e6825 |
| docs/quickstart.md | f0c0b6d2b7fbdd70504ce093f25ed5097dba650d887a94485cd90650f8ce8c5f |
| docs/registration-verification.md | adbd622ef45fa32e91b822d3619dbd2a384648340950e682542ea27d8dd8cd75 |
| docs/user-features.md | 4dba75ca5b900560526dbe1aad179c1dbf6063ad8aefc9b55a4d55a0ece10a18 |
| docs/user_ui.md | 04faef9fc8f3bd8fd9f28885fcde4a4dd77468de46ca916d1e3f4d8f699e67bd |

Initial git status before this new spec:

```text
```
