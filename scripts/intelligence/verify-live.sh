#!/usr/bin/env bash
set -euo pipefail
cd "$(dirname "$0")/../.."
PYTHON=${RELEX_PYTHON:-.venv-c/bin/python}
if [[ ! -x "$PYTHON" ]]; then echo 'BLOCKED R-B1 R-B2 R-B3 R-B4 R-S: set RELEX_PYTHON to backend[intelligence,evidence] environment'; exit 2; fi
PYTHONPATH=backend "$PYTHON" scripts/intelligence/verify-live.py "$@"
