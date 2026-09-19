#!/usr/bin/env bash
set -euo pipefail
cd "$(dirname "$0")/../.."
export PYTHONPATH="$PWD/backend${PYTHONPATH:+:$PYTHONPATH}"
PYTHON="${RELEX_PYTHON:-$PWD/.venv-c/bin/python}"
exec "$PYTHON" scripts/evidence/verify_live.py --component-only "$@"
