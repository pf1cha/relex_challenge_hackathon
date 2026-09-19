#!/usr/bin/env bash
set -euo pipefail
cd /scratch/project_2020551/relex
: "${SLURM_JOB_ID:?Run in an allocated CPU job}"
root="$PWD/.runtime/product"
mkdir -p "$root/pg" "$root/qdrant" "$root/socket"
chmod 700 "$root" "$root/pg" "$root/socket"
pg(){ apptainer exec .runtime/images/postgres.sif "$@"; }
cleanup(){
  for pid in "${webpid:-}" "${qpid:-}"; do if [ -n "$pid" ]; then kill "$pid" 2>/dev/null || true; fi; done
  pg /usr/lib/postgresql/17/bin/pg_ctl -D "$root/pg" -m fast -w stop >/dev/null 2>&1 || true
}
trap cleanup EXIT TERM INT
if [ ! -f "$root/pg/PG_VERSION" ]; then pg /usr/lib/postgresql/17/bin/initdb -D "$root/pg" --auth-local=trust --auth-host=reject; fi
pg /usr/lib/postgresql/17/bin/postgres -D "$root/pg" -k "$root/socket" -p 25433 -c 'listen_addresses=' >"$root/postgres.log" 2>&1 &
pgpid=$!
for i in $(seq 1 30); do if pg /usr/lib/postgresql/17/bin/pg_isready -h "$root/socket" -p 25433 >/dev/null; then break; fi; sleep 1; done
QDRANT__STORAGE__STORAGE_PATH="$root/qdrant" QDRANT__SERVICE__HOST=127.0.0.1 QDRANT__SERVICE__HTTP_PORT=26335 QDRANT__SERVICE__GRPC_PORT=26336 QDRANT__TELEMETRY_DISABLED=true apptainer exec --pwd "$root/qdrant" .runtime/images/qdrant.sif /qdrant/qdrant >"$root/qdrant.log" 2>&1 &
qpid=$!
for i in $(seq 1 30); do if curl -fsS http://127.0.0.1:26335/readyz >/dev/null 2>&1; then break; fi; sleep 1; done
export RELEX_DATABASE_URL="dbname=postgres host=$root/socket port=25433"
export RELEX_QDRANT_URL=http://127.0.0.1:26335
.venv-cpu/bin/python -m uvicorn app.main:app --host 0.0.0.0 --port 28081 --no-access-log >"$root/app.log" 2>&1 &
webpid=$!
printf 'Product on %s:28081 (job %s)\n' "$(hostname)" "$SLURM_JOB_ID"
wait "$webpid"
