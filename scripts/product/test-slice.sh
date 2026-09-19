#!/usr/bin/env bash
set -euo pipefail
cd "$(dirname "$0")/../.."
run_id=""
while (($#)); do case "$1" in --run-id) run_id="$2"; shift 2;; *) exit 2;; esac; done
[[ "$run_id" =~ ^[a-zA-Z0-9_-]+$ ]] || { echo 'Specify --run-id'; exit 2; }
echo 'Development checks only. No product acceptance claims.'
"${RELEX_PYTHON:-.venv-c/bin/python}" -m pytest backend/tests/product -q
cd frontend
npm run typecheck
