#!/usr/bin/env bash
# Foreground launcher for the existing verda development services.
set -Eeuo pipefail
ROOT=$(cd -- "$(dirname -- "${BASH_SOURCE[0]}")/../.." && pwd)
cd "$ROOT"

usage() {
  cat <<'HELP'
Usage: bash scripts/product/start.sh [--port PORT] [--build] [--migrate]

Starts HTTP and the durable worker together; Ctrl-C stops both.
PostgreSQL and Qdrant must already be running. No accounts are created.

Options:
  --port PORT   HTTP port (default: RELEX_PORT or 18080)
  --build       Run npm ci and build the frontend before starting
  --migrate     Apply database migrations before starting
  -h, --help    Show this help

Configuration: exported variables override .env, which overrides defaults.
  RELEX_ENV_FILE            dotenv file (default: repository .env)
  RELEX_PYTHON              Python executable (auto-detect installed environment)
  RELEX_PORT                HTTP port (default: 18080)
  RELEX_HOST                Bind address (default: 127.0.0.1)
  RELEX_DATABASE_URL        Default: postgresql://relex_dev@127.0.0.1:15432/postgres
  RELEX_DATABASE_SCHEMA     Default: manual_demo
  RELEX_QDRANT_URL          Default: http://127.0.0.1:16333
  RELEX_QDRANT_COLLECTION   Default: manual_demo
  RELEX_SESSION_SECRET     At least 32 characters; falls back to saved manual secret
  RELEX_TRUSTED_ORIGINS     Default: http://127.0.0.1:<port>
  RELEX_LOOPBACK_HTTP       Default: 1 (development cookies)
Provider settings use the existing RELEX_MODEL_* / RELEX_EMBEDDING_* variables.
Non-loopback binding requires explicit trusted origins and RELEX_LOOPBACK_HTTP=0
behind an HTTPS reverse proxy.
HELP
}
port_override= build=0 migrate=0
while (($#)); do
  case "$1" in
    --port) [[ $# -ge 2 ]] || { echo '--port requires a value' >&2; exit 2; }; port_override=$2; shift 2 ;;
    --build) build=1; shift ;;
    --migrate) migrate=1; shift ;;
    -h|--help) usage; exit 0 ;;
    *) echo "Unknown argument: $1" >&2; usage >&2; exit 2 ;;
  esac
done

if [[ -z ${RELEX_PYTHON:-} ]]; then
  for candidate in "$ROOT/.tools/miniforge3/envs/relex/bin/python" "$ROOT/.venv/bin/python" "$ROOT/.venv-c/bin/python"; do
    if [[ -x $candidate ]]; then export RELEX_PYTHON=$candidate; break; fi
  done
fi
export RELEX_PYTHON=${RELEX_PYTHON:-python3}
command -v "$RELEX_PYTHON" >/dev/null || { echo 'Set RELEX_PYTHON to an installed backend Python environment.' >&2; exit 1; }
export RELEX_ENV_FILE=${RELEX_ENV_FILE:-$ROOT/.env}
[[ -f $RELEX_ENV_FILE ]] || { echo "Missing dotenv file: $RELEX_ENV_FILE (see .env.example)" >&2; exit 1; }

# Parse dotenv as data, never execute it as shell code. Load only valid variable names.
config=$(mktemp)
trap 'rm -f -- "$config"' EXIT
"$RELEX_PYTHON" - "$RELEX_ENV_FILE" > "$config" <<'PY'
import os, re, sys
from dotenv import dotenv_values
for key, value in dotenv_values(sys.argv[1]).items():
    if re.fullmatch(r"[A-Za-z_][A-Za-z0-9_]*", key) and key not in os.environ and value is not None:
        sys.stdout.buffer.write(key.encode() + b"\0" + value.encode() + b"\0")
PY
while IFS= read -r -d '' key && IFS= read -r -d '' value; do
  export "$key=$value"
done < "$config"
rm -f -- "$config"
trap - EXIT

export RELEX_PORT=${port_override:-${RELEX_PORT:-18080}}
export RELEX_HOST=${RELEX_HOST:-127.0.0.1}
export RELEX_DATABASE_URL=${RELEX_DATABASE_URL:-postgresql://relex_dev@127.0.0.1:15432/postgres}
export RELEX_DATABASE_SCHEMA=${RELEX_DATABASE_SCHEMA:-manual_demo}
export RELEX_QDRANT_URL=${RELEX_QDRANT_URL:-http://127.0.0.1:16333}
export RELEX_QDRANT_COLLECTION=${RELEX_QDRANT_COLLECTION:-manual_demo}
export RELEX_TRUSTED_ORIGINS=${RELEX_TRUSTED_ORIGINS:-http://127.0.0.1:$RELEX_PORT}
export RELEX_LOOPBACK_HTTP=${RELEX_LOOPBACK_HTTP:-1}
if [[ -z ${RELEX_SESSION_SECRET:-} && -f .runtime/manual/env.sh ]]; then
  source .runtime/manual/env.sh
fi
if [[ -d $ROOT/.tools/node-v22.14.0-linux-x64/bin ]]; then
  export PATH="$ROOT/.tools/node-v22.14.0-linux-x64/bin:$PATH"
fi

"$RELEX_PYTHON" - <<'PY'
import os, socket
from app.config import RuntimeSettings
settings = RuntimeSettings.from_env()
port_text = os.environ['RELEX_PORT']
if not port_text.isascii() or not port_text.isdecimal() or not 1 <= int(port_text) <= 65535:
    raise SystemExit('RELEX_PORT must be an integer from 1 to 65535')
host = os.environ['RELEX_HOST']
if host not in ('127.0.0.1', 'localhost', '::1') and settings.http.allow_loopback_http:
    raise SystemExit('Non-loopback binding requires RELEX_LOOPBACK_HTTP=0 and HTTPS trusted origins')
with socket.socket(socket.AF_INET6 if ':' in host else socket.AF_INET) as probe:
    try:
        probe.bind((host, int(port_text)))
    except OSError as exc:
        raise SystemExit(f'Cannot bind HTTP at {host}:{port_text}: {exc}') from None
import psycopg, httpx
with psycopg.connect(settings.database_url, connect_timeout=5) as connection:
    connection.execute('SELECT 1')
response = httpx.get(settings.qdrant_url.rstrip('/') + '/healthz',
    headers={'api-key': settings.qdrant_key} if settings.qdrant_key else {}, timeout=5)
response.raise_for_status()
print('Configuration, HTTP port, PostgreSQL and Qdrant checks passed.')
PY

if ((build)); then (cd frontend && npm ci && npm run build); fi
[[ -f ${RELEX_FRONTEND_DIST:-frontend/dist}/index.html ]] || {
  echo 'Frontend build missing. Rerun with --build.' >&2; exit 1;
}
if ((migrate)); then "$RELEX_PYTHON" scripts/evidence/migrate.py; fi

http_pid= worker_pid=
cleanup() {
  trap - EXIT INT TERM
  for pid in "$http_pid" "$worker_pid"; do
    [[ -z $pid ]] || kill -TERM "$pid" 2>/dev/null || true
  done
  # Bound shutdown if a provider request prevents the worker from exiting.
  for ((attempt=0; attempt<15; attempt++)); do
    if ! kill -0 "$http_pid" 2>/dev/null && ! kill -0 "$worker_pid" 2>/dev/null; then break; fi
    sleep 1
  done
  for pid in "$http_pid" "$worker_pid"; do
    [[ -z $pid ]] || kill -KILL "$pid" 2>/dev/null || true
    [[ -z $pid ]] || wait "$pid" 2>/dev/null || true
  done
}
trap cleanup EXIT
trap 'exit 130' INT
trap 'exit 143' TERM
"$RELEX_PYTHON" -m uvicorn app.main:production_app --factory --host "$RELEX_HOST" --port "$RELEX_PORT" --no-access-log &
http_pid=$!
"$RELEX_PYTHON" -m app.worker &
worker_pid=$!
echo "Starting HTTP (PID $http_pid) and worker (PID $worker_pid). Ctrl-C stops both."
echo "Trusted browser origins: $RELEX_TRUSTED_ORIGINS"
echo "Local tunnel: ssh -N -L $RELEX_PORT:127.0.0.1:$RELEX_PORT verda"
status=0
wait -n "$http_pid" "$worker_pid" || status=$?
echo "An application process exited (status $status); stopping the other process." >&2
# A clean but unsolicited child exit still means the product is no longer running.
((status != 0)) || status=1
exit "$status"
