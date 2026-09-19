# Three-worker implementation plan

Status: delivery plan revision 4, 2026-09-19. Three people implement and test A, B and C concurrently. Policy defaults remain proposals; service contract revision 4 expands the shared interfaces without changing the required product behavior. Read `architecture.md` for code layout, `shared-interfaces.md` and `http-api.md` for interface details, and `independent-testing.md` for standalone acceptance.

This plan does not rely on another checkout's code or delivery contract.

## Source authority and scope

- `../production-behavior.md`: observable requirements, especially evidence, chronology, project access and person deletion.
- `../user-features.md`: document list, citation interaction, project visualization entry point, admin controls and associations.
- `../user_ui.md`: detailed UI requirements. Its broader role/non-project-chat scope differs from the provisional delivery defaults; see the source-compliance section in `shared-interfaces.md`.
- `../ai-agent-architecture.md`: selected technical direction: PostgreSQL authority, Qdrant candidates, three memory levels, separate answer/reviewer contexts, dependency invalidation and application-managed erasure.
- `../database.md`: candidate DBML, not a migration to copy verbatim. Adapt it to versioned records/spans/dependencies. Do not store erased names in purge audit logs; do not require a structured decision ledger or PostgreSQL vectors when the architecture makes statements optional and selects Qdrant.
- `../Pseudo-AI-agent.md`: background only. Do not adopt synthetic human names, HSM deployment, quasi-identifier generalization, or mapping-only erasure. Do not claim legal compliance.

Input SHA-256:

| File | SHA-256 |
| --- | --- |
| production-behavior.md | 8dee98c55acd566612dba1a65c096e5401edadc1746d77eca9175303191e6825 |
| user-features.md | 4dba75ca5b900560526dbe1aad179c1dbf6063ad8aefc9b55a4d55a0ece10a18 |
| ai-agent-architecture.md | 78610a73ef68d218b7c4083516ac76273aa042a082850649f7ffdf504a830952 |
| database.md | a0e4907edbb3b9b11b82ac4b863702e034007864de0cb46bd20da3cbb82d048c |
| Pseudo-AI-agent.md | 1350b4b900b78d322597ab9f67a4185ceaa1c7b582eb4e32fd939a5c2c825244 |

## Proposed implementation defaults

These choices make interfaces implementable. Keep them explicit in the handoff; a change requires a coordinated contract update, not three separate interpretations.

1. Separate `backend/` Python/FastAPI application and `frontend/` TypeScript browser application, with separate dependency manifests and tests. FastAPI may serve the compiled frontend for a single-origin deployment. PostgreSQL is canonical and may run locally alongside the backend on `verda`, accessed directly through a PostgreSQL driver; no hosted database HTTP API is required. Browser requests still use FastAPI. Qdrant supplies retrieval candidates. One model provider may serve the three roles with separate contexts. Use real embeddings of discovered dimension, not a hard-coded DBML vector size. See `architecture.md` for packages, entry points and dependency direction.
2. Project admin manages membership, documents, client/employee associations and project-local person erasure. Member reads active evidence. No system-admin bypass or organization-wide erasure in this slice. A personnel association does not grant a login account access.
3. Real cookie-based login sessions, password hashes, explicit bootstrap command. No caller-supplied user headers as authentication. Production SSO is deferred.
4. Members see opaque person references initially; contacts and identity mapping are admin-only. This resolves the architecture's open rendering choice conservatively. Erased references render as `[deleted user]`.
5. Members cannot browse inactive documents. Admin may inspect current sanitized inactive sources. Old answers with invalid dependencies become unavailable; the delivery contract chooses unavailable/regenerate for changed receipt versions rather than automatic remapping. Superseded decisions remain historical evidence while their sources remain active.
6. Initial import formats: UTF-8 bundled emails, text reports, transcripts. Unsupported formats fail visibly. PDF/OCR is deferred. Preserve title/file identity and source boundaries; sanitize identifying metadata as part of privacy processing.
7. Adopt proposed ingestion removal of residence addresses and non-work private discussion, preserving supported work constraints. Uncertain identity matches or uncertain sensitive spans quarantine the record with an admin recovery path; never silently merge same-name people.
8. Visualization deliverable is project selector and explicitly labeled processing/status information. Actual visualization content remains an open product decision and is not completed by this placeholder.
9. Retained raw/intermediate uploads are restricted and included in the erasure inventory. Corpus input originals outside application-managed storage are not edited. External provider retention/backups must be inventoried as limits; do not promise erasure outside controlled stores.

## Ownership: three parallel implementation slices

| Worker | Outcome | Exclusive paths |
| --- | --- | --- |
| A — evidence platform | Authorized, versioned, privacy-safe evidence and durable lifecycle jobs | `backend/app/evidence/`, `backend/app/contracts/`, `backend/migrations/`, `backend/tests/evidence/`, `backend/tests/contracts/`, `scripts/evidence/`, `docs/implementation/evidence-a.md` |
| B — knowledge and answers | Maintained memories, hybrid search, reviewed claims and history | `backend/app/intelligence/`, `backend/tests/intelligence/`, `scripts/intelligence/`, `docs/implementation/evidence-b.md` |
| C — product and integration | Working authenticated browser/admin flows and assembled application | `backend/app/api/`, `backend/app/__init__.py`, `backend/app/main.py`, `backend/app/bootstrap.py`, `backend/app/config.py`, `backend/app/worker.py`, `backend/tests/product/`, `frontend/`, `scripts/product/`, `fixtures/implementation/`, dependency manifests, `.env.example`, root `README.md`, `docs/implementation/evidence-c.md` |

These are target ownership paths; inspect the current checkout before implementation. A owns schema/contract changes; C owns startup, composition and dependency manifests (including backend packaging/test configuration). Agree independently installable per-slice test dependencies in G0. Subsequent shared dependency changes go through C and contract changes through A; no slice requires another person's running service or completed implementation. Each worker owns package initializers inside its directories. No two workers edit the same file. Specification files are coordinator-owned. No worker edits the five input docs. Do not overwrite `.env` or restore inherited deletions.

## Parallel execution and integration gates

- **G0 — shared starter before parallel implementation:** Check in importable revision 4 DTOs/protocols/errors, contract examples/conformance cases and minimal packaging with per-slice test dependencies. A owns contract files and C packaging; this bounded setup requires no completed A1 or production implementation. The prose below alone is not a completed starter. See `independent-testing.md` for readiness.
- **S-A / S-B / S-C — concurrent standalone acceptance:** All three people implement and test their real slice using substitutes at the other slices' contract boundaries. Each owns fixtures, runner and isolated resources. Tests must run without the other concrete implementations, C's production bootstrap or another person's development server. Standalone acceptance establishes each slice's behavior; G1-G4 establish the assembled product.
- **G1 — first vertical flow:** C accepts an admin upload; A persists a sanitized staged record under a job-scoped internal capability; B reads that staged version, creates memories and indexes it; A verifies dependencies and publishes the coherent version; C opens the source as a member. Staged records are never member/agent-readable. Verify outsider denial. A and B jointly validate the real durable job handler interface for G1; their standalone job tests proceed independently.
- **G2 — reviewed chat:** B supplies search and answer service; C exposes it and renders claim receipts; A supplies final eligibility validation. Run the long-record and chronology cases in Worker B's spec.
- **G3 — lifecycle:** A owns invalidation/erasure coordination, B rebuilds derived artifacts, C exposes job/retry and unavailable states. Run interruption and in-flight invalidation cases.
- **G4 — live acceptance:** C assembles evidence from A/B and runs authenticated browser workflows using real PostgreSQL, Qdrant, generation and embeddings. Each worker reviews the next worker's boundary (A reviews B eligibility; B reviews C receipt rendering; C reviews A lifecycle API) without editing their files. Unresolved failures remain explicit.

After G0, A1-A4, B1-B4 and C1-C4 proceed concurrently. No standalone test or slice handoff waits for another implementation or shared integration fixtures. G1-G4 are separate integration gates, run as real adapters become available. Shared contract changes require a coordinated version update. Coordinator resolves cross-owner changes.

## Shared contract revision 4

The detailed contract is defined in:

- [Shared service interfaces](shared-interfaces.md): DTO fields, exact service methods, access and version rules, reviewed candidates, job capabilities, staging and index-operation acknowledgements.
- [HTTP API and browser contract](http-api.md): request/response types, status codes, cookies/CSRF, route-to-service mapping, browser behavior and independent C fixtures.
- [Synthetic contract examples](contract-examples.json): public responses and error scenarios for G0 schema checks and C fixtures.
- [Independent testing](independent-testing.md): isolated runners, producer/consumer conformance and later G1-G4 integration.

These documents replace the earlier shorthand signatures in this README. A owns the shared implementation of types/protocols/errors; C generates OpenAPI and its frontend client from the actual routes. G0 must turn the specification into importable contracts and validate the examples; documentation alone does not satisfy G0.

The source-compliance section in the service contract records the existing differences between broad UI requirements and provisional delivery scope. Do not silently add global-admin privileges or claim non-project chat/visualization completion. Evidence, project access, chronology, review and erasure requirements remain unchanged.

## Overall completion evidence

Each worker records commands, exit status, relevant IDs/versions, observed outcomes and unresolved failures in its evidence file. Never record credentials or raw personal data in traces. Standalone tests may substitute other slices through shared contracts. B's live acceptance requires real model/reviewer/embedding and Qdrant calls. End-to-end G1-G4 require all real slices, real services and actual browser interactions; fake embeddings or a mock reviewer cannot pass those gates.

Before standalone verification, each person checks their own required services/resources with synthetic data. Before G1-G4, C checks the assembled service/model availability and permitted compute allocation/browser route. Existing old delivery evidence is not current proof. Do not run services/heavy inference on login nodes or assume authorization to send the private corpus to a new provider. Default to synthetic fixtures. Record provider, model ID and embedding dimension safely. Identify unavailable prerequisites precisely rather than fabricating success.

Independent slice handoff requires S-A, S-B or S-C in `independent-testing.md` with cross-slice claims marked integration pending. Overall product success additionally requires all acceptance cases with real adapters and G1-G4. The visualization content deferral and external retention limits remain explicit. This task produces specs only; it does not authorize deployment, dispatch, destructive corpus changes, or publication.
