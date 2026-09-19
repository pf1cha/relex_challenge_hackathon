# Acme corpus verification — 2026-09-19

Result: **FAIL for corpus ingestion; downstream verification BLOCKED.**

Used all 45 original UTF-8 text files under corpus/acme (20 email threads,23 transcripts,2 reports). README and practice questions were reference material, not ingested answer evidence. Original files were not modified; every file hash is retained in the run report.

Actual native PostgreSQL and production evidence/job code were used with the real intelligence adapters and Qdrant configuration. Isolated schema/collection: corpus_20260919_105955. All15 people explicitly listed by the corpus README were associated by full name. No invented identities or privacy bypass was used. Contact values were not inferred or auto-associated.

All45 uploads were accepted and parsed, then failed retryably at parsed with privacy_unresolved. Zero documents published. This occurred before generation/embedding/index writes. It is an actual corpus compatibility failure, not evidence that retrieval or answer quality passed.

Confirmed false-positive examples in transcripts/06_2024-09-24_master-data-workshop.txt: the synthetic disclaimer containing Acme Org, Customer: Acme Org (Grocery Retail, EMEA), Phase: Implementation, and Attendees: with already associated people. Broad name/speaker heuristics treat organization names and metadata headers as unresolved identities. Email files also contain unassociated contacts; those require explicit identity mapping rather than suppression.

Separate actual provider probes returned429 project_spend_limit_exceeded for both generation and embedding. Restoring provider quota alone does not solve the privacy preprocessing failure.

Practice P1–P6/P8–P9: BLOCKED, corpus not published. P7 (Kwame Boateng erasure and P1 rerun): BLOCKED; no indexed/derived corpus exists to erase, so an empty erasure would not prove the requested behavior.

Reproduce:
```bash
cd /mnt/relex-kai
.tools/miniforge3/envs/relex/bin/python scripts/product/verify-corpus.py
```
Each run creates isolated resources; no existing manual-demo data is changed. Safe detailed report: artifacts/corpus/corpus_20260919_105955/report.json. The script reports every per-file status and exits nonzero when ingestion does not pass.

Required next steps: resolve metadata/organization false positives without weakening personal-identity quarantine, explicitly map corpus contacts, restore configured provider quota, then rerun ingestion and all nine citation-backed practice cases against actual services. Do not use source-file reading as a substitute for product answers.
