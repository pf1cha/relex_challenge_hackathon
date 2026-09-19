#!/usr/bin/env bash
set -euo pipefail
cd "$(dirname "$0")/../.."
run_id=""
while (($#)); do case "$1" in --run-id) run_id="$2"; shift 2;; *) exit 2;; esac; done
[[ "$run_id" =~ ^[a-zA-Z0-9_-]+$ ]] || { echo 'Specify --run-id'; exit 2; }
export PATH="/mnt/relex-kai/.tools/node-v22.14.0-linux-x64/bin:$PATH"
export PLAYWRIGHT_BROWSERS_PATH="${PLAYWRIGHT_BROWSERS_PATH:-/mnt/relex-kai/.tools/browsers}"
echo 'Development checks only. No product acceptance claims.'
"${RELEX_PYTHON:-.venv-c/bin/python}" -m pytest backend/tests/product -q
"${RELEX_PYTHON:-.venv-c/bin/python}" scripts/product/development-browser.py
cd frontend
npm run typecheck
