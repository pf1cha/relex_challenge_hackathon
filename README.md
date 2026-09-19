# Memory With a Receipt

Project-scoped document search, reviewed chat and exact source receipts. The Python backend talks directly to PostgreSQL; the browser uses authenticated FastAPI routes. Qdrant is a rebuildable candidate index. The durable worker runs separately from HTTP.

See [Conda and product verification quickstart](docs/quickstart.md) for the installed verda environment.

## Setup

Use Python 3.11+ and Node.js 22+. From the repository root:

```sh
python3 -m venv .venv
.venv/bin/pip install -e './backend[evidence,intelligence,product,test]'
cd frontend
npm ci
cd ..
RELEX_PYTHON=.venv/bin/python bash scripts/product/generate-client.sh
cd frontend
npm run build
cd ..
```

Create private environment configuration from the documented keys in `.env.example`, preserving any existing private `.env`. Set a random `RELEX_SESSION_SECRET` with at least 32 characters. Never commit this value, login passwords, provider credentials or private source data.

PostgreSQL is local to the backend host. Use a native PostgreSQL service/container with persistent storage and an application-owned database/role. Configure `PGHOST`, `PGPORT`, `PGDATABASE`, `PGUSER`, `PGPASSWORD`; optional `RELEX_DATABASE_URL` supplies a native libpq connection string instead. `RELEX_DATABASE_SCHEMA` defaults to `relex`. HTTP and worker must use the same database/schema/secret. Migrations are explicit, not run per HTTP request.

Export the same private database/schema/session configuration in your shell, then run the explicit migration and account/project bootstrap commands. The bootstrap password is prompted:
```sh
.venv/bin/python scripts/evidence/migrate.py
RELEX_SECRET="$RELEX_SESSION_SECRET" .venv/bin/python scripts/evidence/bootstrap.py --email admin@example.test --display-name "Project admin" --project "My project"
```
There are no default login credentials. Account creation and project creation are bootstrap operations; membership assignment never creates a login account.

Configure the authorized generation and embedding endpoints/model IDs, `RELEX_QDRANT_URL`, and an application-owned `RELEX_QDRANT_COLLECTION`. B discovers the embedding dimension from actual embeddings. Do not point development cleanup at somebody else's collection.

For HTTPS set `RELEX_TRUSTED_ORIGINS=https://your-host` and retain secure cookies. For explicit loopback development use `RELEX_LOOPBACK_HTTP=1` and `RELEX_TRUSTED_ORIGINS=http://127.0.0.1:18080`. Secure cookie downgrade is rejected for non-loopback origins.

```sh
.venv/bin/uvicorn app.main:production_app --factory --host 127.0.0.1 --port 18080 --no-access-log
# In another terminal with the same private configuration:
.venv/bin/python -m app.worker
```

The HTTP process serves the compiled frontend and source deep-link shell. `/health` reports actual database/index readiness and model configuration separately; this is not product verification. Job progress survives browser/process restart because A persists it in PostgreSQL. Stop only your owned HTTP/worker process IDs. Keep the database and Qdrant storage for restart tests.

Upload limit defaults to **10 MiB** (`RELEX_UPLOAD_LIMIT_BYTES=10485760`) and is passed to both transport and canonical service. Initial uploads are UTF-8 text: email, transcript, report or specification. PDF/OCR is excluded.

## Development and live verification

The application factory is `app.main.create_app(services, HttpSettings)`; importing it performs no production connections. A/B substitute composition lives only under `backend/tests/product/` and is visibly labeled synthetic. It never becomes an automatic production fallback.

```sh
RELEX_PYTHON=.venv/bin/python bash scripts/product/test-slice.sh --run-id c_dev
cd frontend
npx playwright install chromium
cd ..
RELEX_PYTHON=.venv/bin/python bash scripts/product/verify-live.sh --run-id c_live_one
```

The development runner checks route orchestration and browser types only. The live runner creates a unique `c_live_<run_id>` PostgreSQL schema and Qdrant collection, synthetic accounts, actual HTTP/worker processes and a real Chromium browser. It preserves owned data under `.runtime/c_<run_id>/` for restart inspection and stops only its HTTP/worker PIDs. Its private account/config file is mode 0600; do not commit or publish it. Reports contain safe IDs and observed cases, and identify all remaining blocked/pending requirements. It never substitutes fake models or services.

On the current verda development host, project-local Python is `.venv-c/bin/python`, Node is `.tools/node-v22.14.0-linux-x64/bin`, Chromium is under `.tools/browsers`, PostgreSQL 18.6 listens at `127.0.0.1:15432` with database `postgres`, user `relex_dev`, and Qdrant at `127.0.0.1:16333`. These are isolated synthetic development resources. PostgreSQL's owned data directory is `.runtime/c-postgres/data`; it uses loopback trust, not a production authentication setup. No host services/packages were changed. Verify that these owned processes still run before using them.

## Product limits

Project admin/member roles apply only to explicitly assigned projects. Personnel association is separate from membership. Overview includes an active-record timeline with explicitly labeled L1/L2 discovery summaries and dependency-backed processed-source links; broader aggregate visualization remains deferred. Erasure covers application-controlled stores; downloaded browser content, external provider retention and backups require separate retention handling. The product does not claim full GDPR compliance.
