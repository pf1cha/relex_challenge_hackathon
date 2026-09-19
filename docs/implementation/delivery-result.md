# Three-slice delivery result

Date: 2026-09-19
Authoritative repository: `verda:/mnt/relex-kai`
Frozen delivery spec: revision 4; service contract revision 5.
Baseline: `2063eba9b3f9619653a5b1640b2e87ce725b1c4d`
Reviewed implementation HEAD: `bcae74c5d5c8f72bd1010b4d6a89abf8a19b2302`
Final bounded independent review: **PASS**.

Three implementation workers delivered A (canonical evidence and lifecycle), B (maintenance, retrieval, reviewed intelligence), and C (HTTP/browser composition) in parallel after the shared G0 starter. Implementation was committed in serialized owner-specific checkpoints. No deployment or push was performed.

## Acceptance record

| Requirements | Actual execution evidence |
| --- | --- |
| R-G0 | Importable v5 contracts, inert factories, generated client; A/C reports |
| R-A1 through R-A4 | Real PostgreSQL identity/access, ingestion, persistence, exact receipts, release races, crash recovery, lifecycle and privacy; evidence-a.md and final repairs below |
| R-B1 through R-B4 | Real generation/reviewer/embedding endpoints, PostgreSQL and Qdrant: maintenance, B-C1 through B-C9, negative review, filters, long-record coverage, aggregates and index lifecycle; evidence-b.md |
| R-C1 through R-C4 | Real FastAPI/Chromium authentication, upload/search/chat/source, admin lifecycle, provider recovery, restart and in-flight races; evidence-c.md |
| R-S | Distinct concurrent live instances with separate schemas/collections; A/B/C reports |
| R-G1 through R-G3 | Actual browser-to-canonical-store/index publication, reviewed release and exact source receipts, erasure/recovery/late writes; cross-linked A/B/C reports |
| R-G4 | Assembled real stack, restart, simultaneous A/B/C execution and isolated resources; initial independent review plus bounded repair re-review PASS |

The reports preserve their historical pending statuses and failed attempts. This final record closes the independent-review gate; it does not rewrite an earlier failed or partial runner as PASS. Combined concurrency proved actual overlap and isolation, while behavioral acceptance uses the documented later focused real executions. No full suite or mocked success response was substituted for product verification.

## Independent review and repairs

The initial reviewer independently reproduced three blocking defects. Repair commit `bcae74c5` resolved them:

1. **R-A2/R-A4/I-PRIVACY:** unknown ownership identities could publish and evade later erasure. Identity quarantine and alias-aware inventory now cover those occurrences. The original retained leaked name was removed, its decision preserved with deleted attribution, obsolete vector removed and replacement verified.
2. **R-A4/R-C4:** provider-format failure stranded an erasure with a barrier and no retry. The original `c_late2` job `8f71c03e-2efa-44ef-9d38-c92d8236af53` was retried through authenticated HTTP with the same inventory, then completed and cleared its barrier after cleanup.
3. **R-A2/R-A3/R-C2:** a lifecycle change permanently canceled unrelated accepted uploads. Fresh authorized replacement work now preserves the accepted operation while fencing old capabilities and reconciling outstanding writes. The retained stranded upload completed; focused real late-upsert and replacement-publication restart checks also passed.

The reviewer independently inspected PostgreSQL/Qdrant retained outcomes after repair and reviewed the changed retry/fencing code. No additional blocking defect was found in the accepted findings or directly touched behavior. Independent evidence: `artifacts/review/repair-independent-stores.json`. Worker repair executions: `artifacts/evidence/repair_review_0919/repair.json` and `regressions-final.json`.

Review did not repeat worker suites. Fresh quarantine/association, authenticated retry and paused-writer execution were corroborated through code and retained actual-service evidence; independent probes verified persisted outcomes. All 16 pinned input hashes remain unchanged.

## Explicit limits and remaining interface gap

- Fresh inactive-document library navigation cannot discover a source span under the frozen DTOs. Authorized admin preview works from an existing exact source link. The reviewer withdrew this as an implementation blocker because adding discovery changes the frozen contract. Active-only evidence access was not broadened.
- Conservative identity detection may require admin disambiguation. These synthetic live observations are not a guarantee of model correctness or universal identity recognition.
- Delivery remains project-scoped admin/member and project-grounded chat. Broader source-doc concepts such as global administration, custom roles, general chat and organization-wide erasure are outside this approved delivery scope.
- Actual visualization is deferred. External provider retention, backups, source corpus and previously downloaded browser content remain outside application-controlled erasure. No full GDPR-compliance claim is made.

Owned PostgreSQL at loopback 15432 and Qdrant at loopback 16333, plus isolated synthetic verification state, remain available. C/reviewer temporary HTTP/browser workers were stopped. Private runtime configuration and raw artifacts are not included in the documentation commit. See root README and slice runner documentation for startup.
