#!/usr/bin/env bash
# One-command foreground launcher for the Verda demo stack.
set -Eeuo pipefail
ROOT=$(cd -- "$(dirname -- "${BASH_SOURCE[0]}")/../.." && pwd)
cd "$ROOT"

usage() {
  cat <<'HELP'
Usage: bash scripts/product/start.sh [--port PORT] [--no-build] [--no-migrate] [--prepare-only]

With no flags, discovers the installed Python/Node runtimes, starts the owned
PostgreSQL and Qdrant stores when needed, builds the frontend, applies migrations,
then runs HTTP and the durable worker together. Ctrl-C stops HTTP and the worker;
the local data stores remain available for the next start.

Options:
  --port PORT       HTTP port (default: RELEX_PORT or 18080)
  --no-build        Reuse the existing compiled frontend
  --no-migrate      Do not apply database migrations
  --prepare-only    Start/check stores, build and migrate, then exit
  --build           Accepted for compatibility; building is already the default
  --migrate         Accepted for compatibility; migration is already the default
  -h, --help        Show this help
HELP
}

port_override= build=1 migrate=1 prepare_only=0
while (($#)); do
  case "$1" in
    --port) [[ $# -ge 2 ]] || { echo '--port requires a value' >&2; exit 2; }; port_override=$2; shift 2 ;;
    --no-build) build=0; shift ;;
    --no-migrate) migrate=0; shift ;;
    --prepare-only) prepare_only=1; shift ;;
    --build) build=1; shift ;;
    --migrate) migrate=1; shift ;;
    -h|--help) usage; exit 0 ;;
    *) echo "Unknown argument: $1" >&2; usage >&2; exit 2 ;;
  esac
done

if [[ -z ${RELEX_PYTHON:-} ]]; then
  for candidate in "$ROOT/.tools/miniforge3/envs/relex/bin/python" "$ROOT/.venv/bin/python" "$ROOT/.venv-c/bin/python"; do
    if [[ -x $candidate ]]; then RELEX_PYTHON=$candidate; break; fi
  done
fi
export RELEX_PYTHON=${RELEX_PYTHON:-python3}
command -v "$RELEX_PYTHON" >/dev/null || { echo 'No usable Python environment found. Run scripts/product/setup.sh.' >&2; exit 1; }
export PYTHONPATH="$ROOT/backend${PYTHONPATH:+:$PYTHONPATH}"
for node_dir in "$ROOT/.tools/node-v22.14.0-linux-x64/bin" "$ROOT/.tools/node-v22.14.0-linux-x86_64/bin"; do
  [[ ! -x $node_dir/node ]] || { export PATH="$node_dir:$PATH"; break; }
done

export RELEX_ENV_FILE=${RELEX_ENV_FILE:-$ROOT/.env}
[[ -f $RELEX_ENV_FILE ]] || { echo "Missing dotenv file: $RELEX_ENV_FILE (see .env.example)" >&2; exit 1; }
config=$(mktemp)
trap 'rm -f -- "$config"' EXIT
"$RELEX_PYTHON" - "$RELEX_ENV_FILE" > "$config" <<'PY'
import os, re, sys
from dotenv import dotenv_values
for key, value in dotenv_values(sys.argv[1]).items():
    if re.fullmatch(r"[A-Za-z_][A-Za-z0-9_]*", key) and key not in os.environ and value is not None:
        sys.stdout.buffer.write(key.encode() + b"\0" + value.encode() + b"\0")
PY
while IFS= read -r -d '' key && IFS= read -r -d '' value; do export "$key=$value"; done < "$config"
rm -f -- "$config"; trap - EXIT

export RELEX_PORT=${port_override:-${RELEX_PORT:-18080}}
export RELEX_HOST=${RELEX_HOST:-127.0.0.1}
export RELEX_DATABASE_URL=${RELEX_DATABASE_URL:-postgresql://relex_dev@127.0.0.1:15432/postgres}
export RELEX_DATABASE_SCHEMA=${RELEX_DATABASE_SCHEMA:-manual_demo}
export RELEX_QDRANT_URL=${RELEX_QDRANT_URL:-http://127.0.0.1:16333}
export RELEX_QDRANT_COLLECTION=${RELEX_QDRANT_COLLECTION:-manual_demo}
export RELEX_TRUSTED_ORIGINS=${RELEX_TRUSTED_ORIGINS:-http://127.0.0.1:$RELEX_PORT}
export RELEX_LOOPBACK_HTTP=${RELEX_LOOPBACK_HTTP:-1}
if [[ -z ${RELEX_SESSION_SECRET:-} ]]; then
  if [[ -f .runtime/manual/env.sh ]]; then
    source .runtime/manual/env.sh
  else
    mkdir -p .runtime/manual
    RELEX_SESSION_SECRET=$($RELEX_PYTHON -c 'import secrets; print(secrets.token_urlsafe(48))')
    export RELEX_SESSION_SECRET
    (umask 077; printf 'export RELEX_SESSION_SECRET=%q\n' "$RELEX_SESSION_SECRET" > .runtime/manual/env.sh)
  fi
fi
export RELEX_SECRET=${RELEX_SECRET:-$RELEX_SESSION_SECRET}

start_owned_stores() {
  if ! "$RELEX_PYTHON" - "$RELEX_DATABASE_URL" <<'PY' >/dev/null 2>&1
import psycopg, sys
with psycopg.connect(sys.argv[1], connect_timeout=2) as connection: connection.execute("SELECT 1")
PY
  then
    pg_ctl="$ROOT/.tools/pg/usr/lib/postgresql/18/bin/pg_ctl"
    pg_data="$ROOT/.runtime/c-postgres/data"
    [[ -x $pg_ctl && -d $pg_data ]] || { echo 'PostgreSQL is unavailable and no owned Verda data directory was found.' >&2; exit 1; }
    pg_owner=$(stat -c %U "$pg_data")
    pg_command=("$pg_ctl" -D "$pg_data" -l "$ROOT/.runtime/c-postgres/postgres.log" -o "-h 127.0.0.1 -p 15432 -k $ROOT/.runtime/c-postgres/socket" start -w)
    if [[ $(id -un) == "$pg_owner" ]]; then "${pg_command[@]}"; elif [[ $(id -u) == 0 ]]; then runuser -u "$pg_owner" -- "${pg_command[@]}"; else
      echo "PostgreSQL data belongs to $pg_owner; start it as that user." >&2; exit 1
    fi
  fi
  if ! curl -fsS --max-time 2 "$RELEX_QDRANT_URL/healthz" >/dev/null 2>&1; then
    [[ $RELEX_QDRANT_URL == http://127.0.0.1:16333 ]] || { echo 'Configured Qdrant is unavailable.' >&2; exit 1; }
    mkdir -p .runtime/manual
    nohup bash scripts/intelligence/start-qdrant.sh >> .runtime/manual/qdrant.log 2>&1 &
    qdrant_pid=$!
    for _ in {1..30}; do curl -fsS --max-time 1 "$RELEX_QDRANT_URL/healthz" >/dev/null 2>&1 && break; sleep 1; done
    curl -fsS --max-time 2 "$RELEX_QDRANT_URL/healthz" >/dev/null || { kill "$qdrant_pid" 2>/dev/null || true; echo 'Qdrant did not become ready.' >&2; exit 1; }
  fi
}

start_owned_stores
if ((build)); then
  command -v npm >/dev/null || { echo 'Node.js/npm was not found.' >&2; exit 1; }
  [[ -d frontend/node_modules ]] || (cd frontend && npm ci)
  (cd frontend && npm run build)
fi
[[ -f ${RELEX_FRONTEND_DIST:-frontend/dist}/index.html ]] || { echo 'Frontend build missing.' >&2; exit 1; }
if ((migrate)); then "$RELEX_PYTHON" scripts/evidence/migrate.py; fi

"$RELEX_PYTHON" - <<'PY'
import os, socket
from app.config import RuntimeSettings
settings=RuntimeSettings.from_env();port_text=os.environ["RELEX_PORT"]
if not port_text.isascii() or not port_text.isdecimal() or not 1 <= int(port_text) <= 65535:
    raise SystemExit("RELEX_PORT must be an integer from 1 to 65535")
port=int(port_text);host=os.environ["RELEX_HOST"]
if host not in ("127.0.0.1","localhost","::1") and settings.http.allow_loopback_http:
    raise SystemExit("Non-loopback binding requires HTTPS origins and RELEX_LOOPBACK_HTTP=0")
with socket.socket(socket.AF_INET6 if ":" in host else socket.AF_INET) as probe:
    try: probe.bind((host,port))
    except OSError as exc: raise SystemExit(f"Cannot bind HTTP at {host}:{port}: {exc}") from None
print("Configuration, frontend, migrations, PostgreSQL and Qdrant are ready.")
PY
((prepare_only)) && exit 0

http_pid= worker_pid=
cleanup() {
  trap - EXIT INT TERM
  for pid in "$http_pid" "$worker_pid"; do [[ -z $pid ]] || kill -TERM "$pid" 2>/dev/null || true; done
  for ((attempt=0; attempt<15; attempt++)); do
    ! kill -0 "$http_pid" 2>/dev/null && ! kill -0 "$worker_pid" 2>/dev/null && break
    sleep 1
  done
  for pid in "$http_pid" "$worker_pid"; do [[ -z $pid ]] || kill -KILL "$pid" 2>/dev/null || true; [[ -z $pid ]] || wait "$pid" 2>/dev/null || true; done
}
trap cleanup EXIT; trap 'exit 130' INT; trap 'exit 143' TERM
"$RELEX_PYTHON" -m uvicorn app.main:production_app --factory --host "$RELEX_HOST" --port "$RELEX_PORT" --no-access-log & http_pid=$!
"$RELEX_PYTHON" -m app.worker & worker_pid=$!
echo "HTTP and worker started. Open ${RELEX_TRUSTED_ORIGINS%%,*} (Ctrl-C stops the app)."
status=0; wait -n "$http_pid" "$worker_pid" || status=$?
echo "An application process exited (status $status); stopping the other process." >&2
((status != 0)) || status=1
exit "$status"
