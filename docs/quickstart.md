# Product verification quickstart (verda)

Conda (Miniforge) is installed at /mnt/relex-kai/.tools/miniforge3. The relex environment uses Python 3.12 with backend dependencies installed. Existing .env and virtual environments are preserved; shell startup files are unchanged.

## Activate and check services

Run on the remote host:

```bash
ssh verda
cd /mnt/relex-kai
source .tools/miniforge3/etc/profile.d/conda.sh
conda activate relex
export RELEX_PYTHON="$CONDA_PREFIX/bin/python"
export PATH="/mnt/relex-kai/.tools/node-v22.14.0-linux-x86_64/bin:$PATH"
export PLAYWRIGHT_BROWSERS_PATH=/mnt/relex-kai/.tools/browsers
export RELEX_DATABASE_URL=postgresql://relex_dev@127.0.0.1:15432/postgres
export RELEX_QDRANT_URL=http://127.0.0.1:16333
python --version
python -m pip check
curl --fail http://127.0.0.1:16333/healthz
```

These existing PostgreSQL/Qdrant instances are isolated synthetic development services. If unavailable, restore their owned persistent services before continuing. Health alone does not verify the product.

The app/live runner load existing private .env provider settings. Preserve that file. Generation and embedding endpoints, models and keys are documented in .env.example. Verification uses real provider calls with synthetic documents.

To refresh dependencies and rebuild after code changes:

```bash
python -m pip install -e './backend[evidence,intelligence,product,test]'
(cd frontend && npm ci && npm run build)
```

## Automated real browser verification

```bash
run_id="quick_$(date -u +%Y%m%d_%H%M%S)"
bash scripts/product/verify-live.sh --run-id "$run_id"
run_status=$?
python -m json.tool ".runtime/c_${run_id}/report.json"
printf 'Runner exit: %s\n' "$run_status"
```

Use a fresh run ID. This starts actual HTTP/worker processes and Chromium, exercises login, upload/publication, search, reviewed chat/citations, restart persistence, lifecycle controls and provider outage/recovery. It uses separate PostgreSQL schemas/Qdrant collections and stops its HTTP/worker processes afterward.

- Exit 2 with PARTIAL means executed drivers succeeded, but this runner deliberately does not certify every delivery requirement. Inspect browser, restart, lifecycle, provider_failure and provider_recovery results.
- Exit 2 with BLOCKED means a prerequisite is missing; inspect reason.
- Exit 1 with FAIL means a workflow failed. Inspect driver JSON and services.log. Early exceptions can exit before a complete report exists.

Artifacts are in .runtime/c_<run_id>/. Do not publish private.json: it contains credentials and a signing secret. Earlier full verification and independent review are recorded in [delivery-result.md](implementation/delivery-result.md).

Optional deeper slice checks with the same environment:

```bash
bash scripts/evidence/verify-live.sh --run-id "a_$(date -u +%Y%m%d_%H%M%S)"
bash scripts/intelligence/verify-live.sh --run-id "b_$(date -u +%Y%m%d_%H%M%S)"
```

Read each slice report; their exit/status conventions differ.

## Manual browser demo

After activation/service exports above, create persistent private demo configuration once:

```bash
mkdir -p .runtime/manual
if [ ! -e .runtime/manual/env.sh ]; then
  (umask 077
   printf 'export RELEX_SESSION_SECRET=%s\n' "$(python -c 'import secrets; print(secrets.token_urlsafe(48))')" > .runtime/manual/env.sh)
fi
source .runtime/manual/env.sh
export RELEX_DATABASE_URL=postgresql://relex_dev@127.0.0.1:15432/postgres
export RELEX_QDRANT_URL=http://127.0.0.1:16333
export RELEX_DATABASE_SCHEMA=manual_demo
export RELEX_QDRANT_COLLECTION=manual_demo
export RELEX_LOOPBACK_HTTP=1
export RELEX_TRUSTED_ORIGINS=http://127.0.0.1:18080
python scripts/evidence/migrate.py
RELEX_SECRET="$RELEX_SESSION_SECRET" python scripts/evidence/bootstrap.py \
  --email admin@example.test --display-name 'Project admin' --project 'Manual demo'
```

Bootstrap prompts for your password; run it once for this demo. No default login exists.

In **each** remote HTTP/worker terminal, run this complete setup first. Conda activation alone does not restore application configuration. Bootstrap/migration scripts read exported variables directly; they do not automatically load .env.

```bash
cd /mnt/relex-kai
source .tools/miniforge3/etc/profile.d/conda.sh
conda activate relex
source .runtime/manual/env.sh
export RELEX_DATABASE_URL=postgresql://relex_dev@127.0.0.1:15432/postgres
export RELEX_QDRANT_URL=http://127.0.0.1:16333
export RELEX_DATABASE_SCHEMA=manual_demo
export RELEX_QDRANT_COLLECTION=manual_demo
export RELEX_LOOPBACK_HTTP=1
export RELEX_TRUSTED_ORIGINS=http://127.0.0.1:18080
```

If bootstrap reports /var/run/postgresql/.s.PGSQL.5432, stop it with Ctrl-C and run the setup above before retrying. The owned development database listens on TCP port 15432, not that default socket.

Run one process per terminal:

```bash
# Terminal 1
python -m uvicorn app.main:production_app --factory --host 127.0.0.1 --port 18080 --no-access-log
# Terminal 2
python -m app.worker
```

From a LOCAL terminal:

```bash
ssh -N -L 18080:127.0.0.1:18080 verda
```

Open http://127.0.0.1:18080 and sign in using the bootstrapped account. Use exactly this origin for cookie/CSRF compatibility.

Create a local UTF-8 decision.txt:

```text
On 2026-09-01, the Finland launch was approved for October 2026.
The budget remains undecided.
```

1. Upload as a report; wait for the job to complete.
2. Search Finland and open the canonical source.
3. Ask when the launch was approved. Open the receipt and compare its exact quote with the source.
4. Ask the budget; verify no number is invented.
5. Reload and verify conversation/documents persist.
6. Deactivate the document; after completion its old receipt should be unavailable. Reactivate and verify search returns it again.

Unresolved names can quarantine uploads until admin association and retry. Use synthetic data. Inactive admin previews require an existing exact source link; discovery from a fresh inactive library row is a documented interface gap. Visualization remains deferred.

Stop your HTTP/worker with Ctrl-C and stop the local tunnel separately. Preserve PostgreSQL/Qdrant data for restart checks.
