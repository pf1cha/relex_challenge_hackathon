#!/usr/bin/env bash
set -euo pipefail
cd "$(dirname "$0")/../.."
PYTHON=${RELEX_PYTHON:-.venv-c/bin/python}
if [[ ! -x "$PYTHON" ]]; then echo 'BLOCKED: install backend[intelligence,test] and set RELEX_PYTHON'; exit 2; fi
PYTHONPATH=backend "$PYTHON" scripts/intelligence/develop.py "$@"
