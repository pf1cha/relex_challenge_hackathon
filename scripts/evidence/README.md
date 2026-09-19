# Evidence commands

Install independently: `python -m pip install -e 'backend[evidence]'`.
Use Python 3.11+ and `PYTHONPATH=backend`; select another executable with `RELEX_PYTHON`.
Use `RELEX_DATABASE_URL`, or native `PGHOST/PGPORT/PGDATABASE/PGUSER/PGPASSWORD` when no URL is supplied.
`RELEX_DATABASE_SCHEMA` selects an application-owned schema. `RELEX_SECRET` requires at least 32 random characters and stays stable across restarts.

Migrations: `python scripts/evidence/migrate.py`.
Account/project: `python scripts/evidence/bootstrap.py --email <email> --display-name <name> --project <name>`.
Password is prompted, or `--password-env NAME` reads a private environment variable. No default password exists.

`bash scripts/evidence/test-slice.sh --run-id <unique-id>` runs real PostgreSQL component checks with no concrete B/C imports. This is development evidence.
`bash scripts/evidence/verify-live.sh --run-id <unique-id>` executes the actual A/B services and then advanced/source drivers. It requires real PostgreSQL, Qdrant, generation, independent reviewer and embeddings. Run IDs should use at most 24 alphanumeric/underscore/hyphen characters.
The runner creates disjoint schemas/collections and retains them for inspection; it never truncates application data. Do not reuse run IDs. Remove only run-owned synthetic resources after inspection.

The advanced driver exits actual child worker processes after a committed checkpoint and after real index acknowledgement, waits for test lease expiry, and verifies exact recovery without maintenance regeneration. It also pauses a real index write across erasure, interrupts a dependency route, and retries against the restored real service.
The source driver covers actual bundled emails, quoted forwarding, transcripts, reports, duplicate lineage, uncertain identity quarantine and canonical access denials.

Privacy rules normalize explicitly associated identities/contacts; ambiguous same-name matches and unrecognized speakers/actor names quarantine a record. Admin may add associations and retry or delete it. Optional injected PrivacyDetector receives restricted text outside SQL transactions; uncertain results cannot publish. This does not claim universal identity detection or legal compliance.

A locked PostgreSQL project row is the short transaction boundary for typed canonical records, source spans, artifacts, dependency inventory, durable jobs and answer release. No transaction spans model/index calls. Qdrant content is never canonical. Every public/canonical operation rechecks sessions, access and ownership.
External provider retention, backups, unmanaged original corpus and downloaded browser content remain outside controlled-store erasure.
