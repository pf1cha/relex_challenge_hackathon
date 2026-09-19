#!/usr/bin/env bash
set -euo pipefail
cd "$(dirname "$0")/../.."
export PYTHONPATH="$PWD/backend${PYTHONPATH:+:$PYTHONPATH}"
PYTHON="${RELEX_PYTHON:-$PWD/.venv-c/bin/python}"
if [[ ! -x "$PYTHON" ]] || ! "$PYTHON" -c 'import pydantic, psycopg, psycopg_pool, dotenv' >/dev/null 2>&1; then
  echo 'BLOCKED R-A1/R-A2/R-A3/R-A4: install backend[evidence] in RELEX_PYTHON; see scripts/evidence/README.md' >&2
  exit 2
fi
exec "$PYTHON" scripts/evidence/verify_live.py --component-only "$@"
