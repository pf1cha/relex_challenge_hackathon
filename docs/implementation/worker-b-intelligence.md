# Worker B — maintained memory, retrieval and reviewed answers

Read `README.md`, `architecture.md`, `shared-interfaces.md`, `http-api.md`, `independent-testing.md` and `real-service-verification.md` first. Sources: architecture §§4-8,10,12 and production behavior §4. Own `backend/app/intelligence/` and the other B paths. Depend on injected contract ports, never A's concrete repositories; C composes and exposes your service. Start from G0 contracts with prompts, schemas and owned test fixtures. B owns its live standalone fixtures; C owns shared integration fixtures.

## Verification policy: real services

Verification follows [real-service-verification.md](real-service-verification.md). Run the actual implementation against real PostgreSQL, Qdrant, configured model/reviewer/embedding services, FastAPI and a browser wherever the required operation uses them. Synthetic input documents are encouraged; fake service responses are not acceptance evidence.

Contract tests, schema examples and fixture-service scenarios below are development aids. They may establish implementation readiness but cannot mark product behavior verified. Cross-slice live checks stay pending until real adapters are available. Independent code handoff remains allowed, explicitly labeled implementation-ready rather than live-verified; missing services are reported as blockers, never replaced by a mock pass.


## S-B — independent development and live component verification

Implement B1-B4 while A/C work independently. Use G0 contracts and `independent-testing.md`. Own canonical repository/eligibility/lexical/staging substitutes and sanitized fixtures under `backend/tests/intelligence/`, plus a runner under `scripts/intelligence/`. Do not require A's repositories/migrations or C's server/bootstrap.

Run actual B maintenance, chunking, fusion, expansion, chronology, answer/reviewer and index lifecycle code. Fixture ports supply ordered canonical spans, lexical candidates, version changes and controlled authorization failures; they capture staged outputs. Deterministic mode uses scripted providers for budgets/failures/repairs. Live mode uses the same canonical fixture boundary with real Qdrant, generation, reviewer and embeddings, including B-C1..9.

S-B fixture runs help develop B independently. Verify B's behavior on real model/index services and the real canonical adapter before marking cross-slice requirements passed. SQL lexical retrieval, authorization, publication/release and erasure require the real A/B path. Assert B calls eligibility and rejects stale candidates; do not claim a fixture repository proves production security.

## B1 — evidence-linked memory and real indexing

Implement the registered `process_record` and `rebuild_affected` handlers. Generate level 1 descriptions and level 2 prose/bullet summaries from level 3 sanitized evidence. Attach machine-readable source span/version dependencies, generator version and timestamp. Validate source references before publication. Proposals stay proposals; unsupported owners/dates remain unknown. Summaries cannot independently support final factual claims.

Chunk within one record, preserving ordered stable spans and overlap mappings. Embed the concatenation of level 1, level 2 and that chunk's level 3 text. Use configured real embeddings, discover dimensions and validate collection compatibility. Index payload includes project/document/record/version/chunk/span IDs, topic/person IDs, known dates, publication generation and input hash. Never send identity mappings to the model or store original names in payloads.

Build topic summaries from eligible source evidence, retaining transitive dependencies. Rebuild affected topics on addition/change/lifecycle events, not by continually summarizing the old summary. Build the project overview from current topic summaries with transitive source dependencies and explicit rebuild state; neither overview nor topic summaries can independently support final claims. Propose evidence-linked change notes by comparing related candidates, not every record pair. Review consequential replacement/correction links before publication. All output is staged until A's publication check. Obtain sanitized unpublished input only via A's job-capability port, never ordinary agent source reads. Use revision 5 staged-artifact checkpoints: load before generating, persist before index dispatch, and on retry reuse saved summaries/IDs/timestamps/hashes instead of regenerating them. Exercise CT-17, including resuming the index ledger and rejecting obsolete checkpoints.

Acceptance: two related records produce sourced summaries and a topic overview; an unrelated addition leaves unaffected artifact versions/input hashes unchanged. Model-produced invalid span IDs prevent publication. Inspect real embedding requests/dimensions and current Qdrant payloads. Repeating a summary across chunks must be reflected in their input hashes.

Base-record extraction/index publication precedes aggregate rebuilds. Aggregate jobs read a published snapshot and fail/retry on changed dependencies. The public overview must pass independent claim-level grounding against source spans before release; raw level-2 memory remains internal. Verify an unsupported overview clause is withheld even when its dependency IDs exist.

## B2 — one scoped hybrid search and complete record reading

Combine PostgreSQL lexical retrieval and Qdrant semantic candidates using reciprocal-rank fusion as the initial configurable default. Deduplicate overlapping chunks and parent records. Apply every shared filter, then revalidate candidates against A's canonical eligibility; stale/wrong-project payloads never become source text. Name queries resolve to person IDs only through A's restricted authorized operation.

Search identifies parent records. Explicitly read all sibling chunks from the selected record/version in source order, including low-ranked chunks; pagination reports total chunks, returned IDs, completion and cursor. Do not expand the whole original bundled file accidentally. Track candidate IDs separately from passages actually supplied to the model. Budgets disclose incomplete coverage and withhold dependent current-state conclusions.

Implement answer/reviewer tools: `search_memory`, `read_record`, `read_memory`, `get_decision_history(topic_id, scope, as_of)`, `expand_context(record_id, span_id)`. Agent arguments cannot supply user/project permissions or arbitrary SQL. Tool calls carry server-bound context; document instructions are untrusted data.

Acceptance: each filter individually and in combination; exact lexical-only identifier; semantic paraphrase; matching early chunk with a late qualification; ordered pagination and exhausted budget; stale cursor; wrong-project/stale Qdrant entries; a bundle where only the selected record expands. Demonstrate normal search and agent tools share eligibility behavior.

## B3 — chronology and bounded answer workflow

Use at most three initial answer search/retrieval rounds and one review-driven repair cycle as configurable defaults, with separate phase budgets defined below. A round may paginate selected records within its page/token budget. Retrieve relevant later changes as well as the initial match. Store evidence-linked history by topic/scope with source time, effective time and learned time distinct. Never infer authority solely from upload time, document type, repetition or a model confidence score.

Account budgets separately: initial answer has up to three search rounds, targeted repair has one additional search round, and each of at most two reviewer passes has up to three independent search rounds. Use explicit finite tool/page/token caps per phase and a request-wide deadline; log every counter. The repair allowance is deliberate, not a reset of the initial budget. Exhaustion withholds dependent claims and never bypasses review. Fix fixture dates to year 2026 with an explicit timezone where present; as-of uses supported effective time, not what the system knew at ingestion time.

Build structured draft claims and receipts from canonical source spans plus relevant counterevidence. No narrative factual text bypasses the claim list. If support, chronology or coverage is insufficient, state the limitation and return supported partial content only. Unknown facts are not generated.

Normalize the question and supplied conversation history through A before provider calls. History helps interpret follow-ups but supplies no evidence; reread current sources. Include supported proposer, agreeing parties, owner, due date, scope and conditions in commitment claims; explicitly mark requested missing details unknown. Add a fixture where mentioning someone does not make them the owner, plus a follow-up after a new correction.

Acceptance fixtures, with fixed dates/scopes and semantic expected outcomes:

| ID | Evidence | Required result |
| --- | --- | --- |
| B-C1 | October accepted; later November proposed | October is agreed; November remains proposal, cite both |
| B-C2 | October effective Sep 1; explicitly replaced by November effective Sep 10 | As of Sep 5: October; Sep 15: November, with replacement receipt |
| B-C3 | Report claims agreement; explicit correction says it never happened | Incorrect/never-true assertion, not a previously valid agreement |
| B-C4 | Newer explicit replacement ingested before older original | Effective decision history, not upload order, governs |
| B-C5 | No budget evidence | Cannot establish budget; no invented number/owner |
| B-C6 | Incompatible agreements, no replacement/authority rule | Unresolved conflict with both receipts |
| B-C7 | Different Finland/Sweden commitments | Independent scopes; neither supersedes the other |
| B-C8 | Forwarded proposal and duplicate copies | Original speaker attribution; no invented acceptance |
| B-C9 | Unknown effective date or unread late qualification | Explicit uncertainty/incomplete coverage, no false current certainty |

## B4 — independent grounding and lifecycle hooks

Reviewer uses a separate context, no draft agent reasoning, canonical sources/history/counterevidence, and its own read-only tools. It can search beyond the draft's selected passages. Return per-claim `{claim_id, verdict, reason_code, receipt_ids, repair_request}`. Reasons include missing support, attribution mismatch, proposal as agreement, missing condition, stale as current, citation mismatch. Verify every factual clause.

Application checks span existence, quote equality, source versions and dependencies independently of the reviewer. One targeted repair may retrieve/rewrite failed claims, followed by a fresh review. Omit unresolved failed claims or return inability. Provider/reviewer failure must never become a verified answer. C receives only reviewed candidates; A's final gate is still required before rendering/persistence. Stream progress only, never unreviewed factual claims.

Implement idempotent derived-data rebuild/removal for A's lifecycle jobs. Re-embed every changed input, including repeated summaries; preserve unchanged inputs. Remove obsolete vectors and payloads. Provide durable per-entry old/new hash, model/dimension and completion status without personal content. Reconciliation detects orphaned/stale index entries and incomplete jobs.

Record content-safe tool/result IDs, versions, grounding reason codes, repair count, latency and token usage. Report retrieval coverage, citation validity, stale-as-current and attribution failures separately. Include topic and project-overview dependencies in every lifecycle rebuild and reconciliation check.

Bind each review result to the exact candidate claim/receipt digest; editing text after review requires re-review. Return ReviewedCandidate through the shared contract, not a pre-persisted Answer. Index writes use version-specific point IDs, durable operation tracking and A-issued lease/lifecycle tokens. Explicitly implement `remove_index_entries` and reconciliation. Test a delayed pre-erasure upsert; report no cleanup success until its outcome is resolved and any obsolete point is removed.

Acceptance: real reviewer rejects deliberately unsupported attribution and a stale draft whose correction it finds outside the supplied packet; capture safe tool IDs and per-claim verdicts. Show normal public chat uses this gate. Force provider unavailability, budget exhaustion, bad citations and second review failure. During A erasure/deactivation, old content remains ineligible; rebuild replaces every changed entry and leaves unrelated hashes intact.

## Done and dispatch prompt

Record B1-B4 and B-C1..9 in `evidence-b.md`: actual model outputs, semantic assertions, prohibited claims, receipts, safe tool traces and failed attempts. Model stubs and fixture repositories support development only. Live behavioral acceptance requires real model/reviewer/embedding and Qdrant calls plus real A repository adapters for canonical persistence/retrieval. G1-G4 also require the actual C application. Do not hide failed first attempts behind successful retries.

> Implement Worker B in `/mnt/relex-kai` using this file and the shared README. Start from G0 contracts; implement B1-B4 and run S-B independently while A/C implement their slices. Use A's repository and eligibility interfaces and C's route composition. Own only B paths. Verify real retrieval, chronology and independent review with synthetic fixtures; preserve source docs and do not dispatch descendants or change another checkout.
