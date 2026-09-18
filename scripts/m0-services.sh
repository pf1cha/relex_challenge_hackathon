#!/usr/bin/env bash
# Run only within an allocated CPU compute job. Owned data/ports only.
set -euo pipefail
cd /scratch/project_2020551/relex
: "${SLURM_JOB_ID:?Run using the documented Slurm CPU allocation}"
[ "$(uname -m)" = x86_64 ] || { echo 'CPU x86_64 allocation required'; exit 1; }
root="$PWD/.runtime/m0"
mkdir -p "$root/pg" "$root/qdrant" "$root/socket"
chmod 700 "$root" "$root/pg" "$root/socket"
pg() { apptainer exec .runtime/images/postgres.sif "$@"; }
cleanup() {
  if [ -n "${qpid:-}" ]; then kill "$qpid" 2>/dev/null || true; wait "$qpid" 2>/dev/null || true; fi
  pg /usr/lib/postgresql/17/bin/pg_ctl -D "$root/pg" -m fast -w stop >/dev/null 2>&1 || true
}
trap cleanup EXIT
if [ ! -f "$root/pg/PG_VERSION" ]; then
  pg /usr/lib/postgresql/17/bin/initdb -D "$root/pg" --auth-local=trust --auth-host=reject
fi
start_pg() {
  pg /usr/lib/postgresql/17/bin/postgres -D "$root/pg" -k "$root/socket" -p 25432 -c "listen_addresses=" >"$root/postgres.log" 2>&1 &
  pgpid=$!
  for i in $(seq 1 30); do
    if pg /usr/lib/postgresql/17/bin/pg_isready -h "$root/socket" -p 25432; then return; fi
    kill -0 "$pgpid" || { cat "$root/postgres.log"; return 1; }
    sleep 1
  done
  return 1
}
start_qdrant() {
  QDRANT__STORAGE__STORAGE_PATH="$root/qdrant" QDRANT__SERVICE__HOST=127.0.0.1 QDRANT__SERVICE__HTTP_PORT=26333 QDRANT__SERVICE__GRPC_PORT=26334 QDRANT__TELEMETRY_DISABLED=true apptainer exec --pwd "$root/qdrant" .runtime/images/qdrant.sif /qdrant/qdrant >"$root/qdrant.log" 2>&1 &
  qpid=$!
  for i in $(seq 1 30); do
    if curl -fsS http://127.0.0.1:26333/readyz >/dev/null; then return; fi
    kill -0 "$qpid" || { cat "$root/qdrant.log"; return 1; }
    sleep 1
  done
  return 1
}
start_pg
pg /usr/lib/postgresql/17/bin/psql -h "$root/socket" -p 25432 -d postgres -v ON_ERROR_STOP=1 -c "CREATE TABLE IF NOT EXISTS relex_m0 (id integer PRIMARY KEY, value text); INSERT INTO relex_m0 VALUES (1, 'persistence-probe') ON CONFLICT (id) DO UPDATE SET value=EXCLUDED.value;"
pg /usr/lib/postgresql/17/bin/pg_ctl -D "$root/pg" -m fast -w stop
start_pg
pg /usr/lib/postgresql/17/bin/psql -h "$root/socket" -p 25432 -d postgres -v ON_ERROR_STOP=1 -c 'SELECT version(),value FROM relex_m0 WHERE id=1;'
start_qdrant
curl -fsS http://127.0.0.1:26333/
curl -fsS -X PUT http://127.0.0.1:26333/collections/relex_m0 -H 'Content-Type: application/json' -d '{"vectors":{"size":3,"distance":"Cosine"}}'
# Disposable service-persistence vector only; this is not an embedding/model acceptance probe.
curl -fsS -X PUT 'http://127.0.0.1:26333/collections/relex_m0/points?wait=true' -H 'Content-Type: application/json' -d '{"points":[{"id":1,"vector":[1,0,0],"payload":{"probe":"persistence"}}]}'
kill "$qpid"; wait "$qpid" || true; qpid=''
start_qdrant
curl -fsS http://127.0.0.1:26333/collections/relex_m0/points/1
curl -fsS -X DELETE http://127.0.0.1:26333/collections/relex_m0
printf '\nM0 service persistence passed on %s; services stop on exit.\n' "$(hostname)"
