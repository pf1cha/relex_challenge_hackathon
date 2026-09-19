# Worker B implementation and live evidence

Delivery revision 4 (frozen), service contract 5. Baseline `2063eba9b3f9619653a5b1640b2e87ce725b1c4d`. Authoritative checkout `/mnt/relex-kai` via `ssh verda`. Initial HEAD matched baseline; all inherited implementation-document edits were preserved. First B implementation commit: `5817458`. This report distinguishes executed observations from remaining acceptance; it is not independent reviewer approval.

Status: **implementation-ready; live verification partially completed**. The complete slice is not marked live-verified. Unexecuted scenarios below remain pending even though many real workflows passed. No contract/fixture pass is counted as product acceptance.

## Implementation

Owned code provides injected maintenance/retrieval/answer services, real OpenAI-compatible generation and embedding transport, real Qdrant REST indexing, per-record chunk slices, signed context/query/filter cursors, canonical candidate validation, record expansion with actual supplied-chunk coverage, separate finite answer/repair/reviewer budgets, independent reviewer discovery, exact canonical receipts and candidate digests, omission proofs, topic/overview generation with source dependencies, durable checkpoint reload, immutable entry IDs, operation-ledger reports, idempotent removal and reconciliation reporting. Imports do not load configuration or import concrete A/C packages.

Maintenance checkpoints are loaded before generation and saved before preparing index writes. A saved batch's IDs, summaries, timestamps, input hashes/model/dimension are reused. Unknown operations are not assumed canceled; absent points alone do not resolve old possible writers. Aggregate overview prose is routed through source-grounded claims and review before A releases it. Model dates such as an unqualified month name become explicit unknown dates rather than an invented year. Noncontiguous source references become separate exact contiguous receipts.

Development substitutes are confined to `backend/tests/intelligence/`. `scripts/intelligence/test-slice.sh` labels these runs DEVELOPMENT_ONLY, including its real-provider mode. `verify-live.sh` imports actual A/PostgreSQL adapters and actual B model/index code; it never imports those substitutes. See `scripts/intelligence/README.md` for setup, runtime ownership, isolated names and command semantics.

## Actual services and owned resources

- PostgreSQL 18.6: C-owned loopback service `127.0.0.1:15432`, database `postgres`, role `relex_dev`; B owns only schemas prefixed `b_live_` for its run IDs.
- Qdrant 1.14.1, commit `530430fac2a3ca872504f276d2c91a5c91f43fa0`: B-owned PID 18621, loopback HTTP 16333 / gRPC 16334. Persistent storage is `scripts/intelligence/runtime/storage`; runtime is ignored and not committed. B live collections match their schema names. Other workers use their own collections.
- Actual configured generation/reviewer model: `gpt-5.4-mini`; embedding model: `text-embedding-3-small`; actual dimension 1536. Separate role contexts use the configured provider. Only synthetic input records were sent. API keys were never printed or committed.
- Retained evidence: `scripts/intelligence/runs/<run-id>/live.json`. Private per-run signing keys are ignored chmod-600 files. Schemas, collections and safe source/object IDs are retained for independent inspection; no cleanup touched another worker's data.

## Commands and observed outcomes

All commands ran on `verda` from `/mnt/relex-kai` with `RELEX_LIVE_DATABASE_URL=postgresql://relex_dev@127.0.0.1:15432/postgres` and C's `.venv-c` Python. The live runner exits 3 after successful requested execution because it deliberately does not equate that subset with complete acceptance. Exit 2 records actual failures/blockers. Each report records HEAD/time/resource IDs and original model outputs.

| Command suffix after `bash scripts/intelligence/verify-live.sh` | Observation |
| --- | --- |
| `--run-id b_all_cases` | Ten cases B-C1..B-C9 plus B-OWNER executed on real PostgreSQL/model/reviewer/embedding/Qdrant. Every answer was atomically released by A, reread through a new A/PostgreSQL adapter, and checked against canonical receipt quotes. Same request replay returned the same answer; changed input under the key returned idempotency_conflict. 247 provider events retained. |
| `--run-id b_isolated_two --case B-C9` | Ran concurrently with b_all_cases using disjoint schema/collection and report directory; real uncertain/conditional answer persisted. R-S isolation observed. |
| `--run-id b_negative --case B-C1 --negative` | Real reviewer rejected deliberately invented PERSON_Z / EUR 7,000,000 / ownership with attribution_mismatch. Actual refused loopback provider connection returned provider_unavailable, no claims. One-unit source/tool budget returned empty inability with budget_exhausted coverage. A rejected an altered receipt quote from an actual reviewed candidate. |
| `--run-id b_stale --case B-C3 --stale` | Real reviewer rejected a draft claiming October is current, reason stale_as_current. Proposed citations contained only the original report; independent searches added the separate correction record to dependencies and located “never happened” evidence. |
| `--run-id b_retrieval_v2 --retrieval` | Real long record yielded 25 ordered source pages. Exact ZXQ-771 lexical candidates existed; type, source, lower/upper date, person, topic and combined filters returned the canonical record, wrong type returned none. A rejected a deliberately inserted version-999 Qdrant candidate; actual shared search returned no stale version. Final reviewed answer said the launch was not accepted and cited the late qualification. Noncontiguous supports were emitted as separate exact receipts. |
| `--run-id b_aggregate --case B-C1` | Both ingests completed and current overview was ready with reviewed claims. An earlier aggregate job failed evidence_changed after the second publication; the newly scheduled aggregate completed against current dependencies. This is visible stale-snapshot rejection, not a hidden retry/pass. |

Semantic inspection of b_all_cases (original answer/receipt/digest objects remain in the report):

| Case | Actual claim meaning; prohibited conclusion absent |
| --- | --- |
| B-C1 | October agreed by PERSON_A/PERSON_B; November only proposed, no acceptance. No November agreement invented. |
| B-C2 | September 5: October effective September 1. September 15: November replacing October effective September 10. |
| B-C3 | Correction says reported October agreement never happened; does not call it a previously valid agreement. |
| B-C4 | November current effective September 10 despite older original being ingested second. |
| B-C5 | Budget and owner cannot be established; no invented amount/owner. |
| B-C6 | Both incompatible agreements cited, unresolved conflict retained; no automatic newest-wins rule. |
| B-C7 | Finland October and Sweden November remain independent scopes. |
| B-C8 | PERSON_A is original proposer; acceptance not recorded. Forwarder/duplicate not promoted to agreement. |
| B-C9 | Unknown effective date, October option, capacity verification/acceptance absent; no false current commitment. |
| B-OWNER | Ownership remains unassigned; mentioning PERSON_B does not establish ownership. |

The isolated inability cases use fixed operational outcome fields and only supported factual clauses. These observations establish these specific cases, not a general guarantee of model correctness.

## Failed first attempts and fixes

- bfirst/bsecond: actual aggregate model supplied invalid effective_at shape; safe validation prevented publication. Prompt now spells out SourceTime; unsupported date precision remains unknown. bsecond retains safe validation locations.
- bthird: workflow reached actual persisted answer; verifier called the receipt method on EvidencePlatform instead of its reader port. Harness accessor fixed; b_all_cases replayed successfully.
- b_retrieval: actual model selected nonadjacent first/last source spans in one evidence reference. Canonical contract validation rejected the draft. B now splits noncontiguous supports into separate exact receipts before independent review; b_retrieval_v2 completed.
- A's advanced live erasure probe encountered model month “December” without a year. B now preserves unknown effective time and maps malformed model DTOs to safe contract_violation without raw validation text. A reruns its actual lifecycle case; see evidence-a.md for its outcome.

The extra retained-resource probe first hit a verifier-only list-vs-method typo; it restored the actual vectors in a finally block, and `retrieval-extra-first-failed.json` retains that failure before the corrected run. C also found a real empty-corpus model clause without references after provider restoration; B now returns fixed no_evidence immediately after empty canonical retrieval, before drafting. C owns the focused actual HTTP recovery recheck. Failed first attempts are retained separately.

## Requirement and scenario coverage

| Requirement/scenario | Evidence / outstanding status |
| --- | --- |
| R-G0 inert imports | Actual imports passed with no app.evidence/app.api modules loaded; pure unknown-date handling and compileall also passed. Supplemental development checks only. |
| R-B1 two related sourced record memories, real embeddings/index, reviewed topic overview | b_all_cases and b_aggregate; actual model IDs/dimension, source versions, batch/index IDs, quotes and current reviewed overview. |
| R-B1 repeated summary input hashes and actual checkpoint/crash recovery (CT-17) | Code reconstructs exact saved embedding input. A owns real subprocess crash-before-index / crash-after-ack probes using actual B; acceptance links to evidence-a.md when recorded. B fixture checkpoint replay is development evidence only. |
| R-B1 unrelated addition preserves unaffected artifact version/hash | Actual unrelated-source publication preserved all 25 prior record index payloads/hashes/vectors (`retrieval-extra.json`). Unchanged-topic artifact timestamp/version preservation after aggregate rebuild remains pending; code reuse alone is not proof. |
| R-B1 invalid model span IDs prevent publication; unsupported overview clause withheld | Validation/review implemented; **explicit malformed-span and unsupported-overview live probes pending**. Ordinary reviewed overview is observed, not this negative scenario. |
| R-B2 all filters, ordered late qualification, stale candidate | b_retrieval_v2: eight positive filter combinations, negative type filter, 25 pages, version-999 rejection, actual final receipts. |
| R-B2 lexical-only, semantic paraphrase, stale cursor, wrong-project payload | Additional actual probe `probe-existing.py --run-id b_retrieval_v2` temporarily removed only its owned real Qdrant entries, preserved the PostgreSQL lexical hit, and restored the exact real vectors. Actual paraphrase embedding/Qdrant query found candidates. Wrong-project injected point was rejected; source cursor after unrelated publication returned stale_cursor. Report `retrieval-extra.json`. Isolated semantic-only fusion and bundled selected-record-only expansion remain pending. |
| R-B2 exhausted coverage | b_negative produced budget_exhausted and no factual claims. |
| R-B3 B-C1..9 and mention-is-not-owner | b_all_cases observed outcomes above with real independent review and exact receipts. |
| R-B3 follow-up after newly ingested correction | `probe-existing.py --run-id b_all_cases --case B-C1 --followup`: added an actual correction after the saved answer; old answer returned answer_unavailable, A supplied only the eligible user history, and new reviewed answer said October never happened / November unaccepted. `followup.json` retains actual history and receipts. |
| R-B4 independent unsupported/stale review, exact digest/quotes, provider failure, budget failure | b_negative, b_stale; actual persisted ordinary candidates and A malformed-quote rejection. |
| R-B4 second reviewer failure / omission projection | b_all_cases actually exercised three repairs. B-C3 final review retained one supported claim and omitted one stale_as_current failure (2 -> 1); B-C4 retained two supported claims and omitted missing_support (3 -> 2). Actual omission proofs with distinct reviewed/final digests were accepted by A and persisted; full proofs remain in each case candidate. |
| R-B4 index replacement/removal, erasure repeated-summary recomputation, late upsert, reconciliation | Real callbacks implemented; A/C own actual lifecycle/drain/late-writer probes and SQL/index inspection. Link evidence-a.md / evidence-c.md; no B fixture callback counted as success. |
| R-S independent setup and real isolated runs | Owned runners/resources. b_all_cases and b_isolated_two overlapped with disjoint actual schemas/collections. Other implementation packages are absent from production B import graph; live runner explicitly requires real A. |
| R-G1..G4 / browser | C owns actual browser flow and simultaneous A/B/C live run; link evidence-c.md. B ordinary service execution is not browser evidence. |

Actual visualization content remains deferred. External provider retention/backups/downloaded browser content remain limits; this report makes no full GDPR-compliance claim. Independent review and the explicitly pending scenarios are required before declaring the whole product complete.
