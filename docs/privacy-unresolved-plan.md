# Privacy quarantine diagnosis and proposed repair

Status: proposal only; no implementation changes.
Investigated: 2026-09-19, authoritative verda:/mnt/relex-kai.

## Observed failure

All45 Acme corpus files previously reached parsed and failed privacy_unresolved before model/embedding/index publication. A read-only replay of the current normalize function with the actual retained project's15 registered identities flagged1436 of15939 source lines across20 email threads,23 transcripts and2 reports. These are flagged-line counts, not1436 proven personal-data leaks. The project's registered contact count is0.

Evidence: artifacts/corpus/privacy-diagnosis.json and artifacts/corpus/corpus_20260919_105955/report.json. Source corpus and implementation were unchanged.

## Causal trace

jobs.py prepare_ingestion parses raw input into line spans and initializes records unpublished/quarantined. At parsed it normalizes each raw span and filename. Any ambiguous result sets one upload-wide unresolved flag; the job fails retryably with privacy_unresolved and never reaches privacy_ready. This intentionally blocks downstream maintenance/indexing.

privacy.py normalize first replaces registered display names/contact aliases with opaque person IDs. It then:
- replaces unmapped emails/phones with unresolved-contact markers and flags uncertainty;
- classifies title-case word sequences as unknown names;
- applies owner/attribution/verb rules;
- interprets name-shaped prefixes followed by a colon as speakers.

The normal production bootstrap supplies no privacy_detector. The optional detector path exists but is not configured. Even when supplied, detected names are checked against exact display names, and the same regex checks still run afterward; simply plugging in a detector cannot override the present false positives.

## Root causes

1. Entity classification conflates organizations, roles and people. Acme Org, Grocery Retail, Meridian Consulting and Service Delivery match broad name-shaped expressions. A short suffix exception list does not constitute organization recognition.
2. Metadata and conversation speakers share one regex path. Phase: Implementation and Decision: October rollout approved are flagged as speakers. Attendees remains flagged even after all listed people have been correctly replaced by opaque IDs. Adding labels to a skip list without scanning their values would risk leaking real names.
3. Identity setup is incomplete. Full-name registration does not register email, phone, first-name or other aliases. A line From: Ana Duarte normalizes successfully; the same name plus an unmapped email is quarantined. The corpus verification fixture used15 names and0 contacts. These are genuine unresolved associations under the current policy, not all false positives.
4. Processing is line-local. It cannot reliably use an email header/signature block or a transcript's participant/speaker/timestamp structure to resolve references. Contacts outside the same line are unavailable for same-name disambiguation.
5. Diagnostics collapse all causes into one boolean/error. Admins cannot distinguish unknown contact, ambiguous identity, organization misclassification or header handling, nor locate the offending occurrence through the normal job UI.
6. Detection is also incomplete: ASCII-oriented name rules and narrow templates do not provide general identity detection. Removing broad checks alone would reopen the independently reproduced owner-position name leak.
7. The general multiword-name quarantine was introduced in repair bcae74c after a real unknown-owner identity escaped ingestion/erasure. Verification covered synthetic owner and same-name cases but not the supplied corpus. Existing metadata-prefix behavior predates that repair. This was an inadequate representativeness check.

Related behavior: unresolved is upload-wide and cumulative across records. A single ambiguous span blocks the entire upload; per-record quarantined flags can depend on iteration order. Keep upload publication atomic for this repair and calculate per-record flags independently for coherent diagnostics, without introducing partial publication.

## Proposed implementation sequence

1. Add structured, restricted diagnostics first.
   Emit reason code, record/span/location and candidate type for every unresolved occurrence. Keep original values admin-only with the same erasure/retention controls as raw sources; do not add raw names to public job errors/logs. Extend explicit internal DTO/admin API contracts for a resolution UI rather than overloading the boolean. Suggested reasons: unknown_person, unmapped_contact, conflicting_identity, uncertain_entity. Existing safe public job code can remain privacy_unresolved.

2. Introduce format-aware preprocessing with original offsets preserved.
   Identify email address lists/signature blocks and transcript metadata/speakers/timestamps. Treat metadata labels as structure, but inspect every value for people/contacts. Recognize organization/role spans separately from person candidates. Preserve original source spans, dates and citation locations; do not remove disclaimers/headers just to make the run pass.

3. Resolve identities from evidence, not capitalization.
   Retain exact known aliases and opaque person IDs. Parse explicit display-name/address pairs as proposed contact associations; validate consistency and require admin confirmation for conflicting/shared or uncertain mappings. Support explicit name aliases separately from contact types. Resolve shortened references only with sufficient scoped evidence; never merge same-name people or infer ownership from mention. Do not whitelist Acme names, rename organizations as people, or blindly map first names.

4. Replace blanket heuristics with typed entity decisions.
   Deterministic format parsing and confirmed person/organization mappings should handle known structure. Any additional entity detector should be local or separately authorized for raw preprocessing input; the existing shared detector contract needs explicit entity classification/context extensions if used for organization discrimination. Evaluate that bounded choice against the corpus before selecting it. Unknown human attribution such as The owner is Alice Example must still quarantine. Non-person spans may pass only with a supported classification; uncertain cases remain reviewable.

5. Make resolution and same-job retry usable.
   Show admin-only unresolved occurrences with classify/associate actions and supporting context. Persist decisions and their provenance. Retry must recompute from restricted raw spans under a fresh people snapshot, retain source positions, and publish only after all required privacy checks pass. Keep erased identities/alias decisions within cleanup inventory. Restrict any non-person classification to the verified occurrence/context so a later genuine name is not globally exempted.

6. Verify with staged, real acceptance.
   First reproduce current failures with a small matrix: metadata, organizations, mapped full name, name+unmapped email, multiple recipients with an unknown later recipient, shared-name contacts, Unicode names, unknown-owner attribution, and operational facts. Ensure known false positives disappear while leak cases remain quarantined.
   Then rerun all45 original files with an explicitly reviewed roster/contact manifest. Every remaining quarantine needs a documented genuine unresolved occurrence, not a blanket success target or automatic bypass. Verify no names/contacts reach maintenance/embedding requests.
   Once provider quota is restored, execute real publication, search, P1–P6/P8–P9 answers with exact citations, and P7 Kwame erasure plus P1 rerun. Inspect PostgreSQL/Qdrant and late-writer/restart behavior for changed privacy dependencies. Preserve failed runs; no answer read directly from the corpus counts as product verification.

## Completion and dependencies

Local parsing/classification/diagnostic work can proceed without provider quota. Actual publication, retrieval, answer and erasure acceptance cannot: independent real generation and embedding probes returned429 project_spend_limit_exceeded.

Do not combine this repair with the relational-schema migration or alter the original corpus. Expected user-visible outcome is actionable quarantine for genuinely ambiguous identities, successful safe ingestion of correctly classified metadata/organizations, and preserved decision/citation/erasure semantics. Zero quarantine is not itself the success criterion.
