#!/usr/bin/env bash
set -euo pipefail
cd "$(dirname "$0")/../.."
run_id=""
while (($#)); do case "$1" in --run-id) run_id="$2"; shift 2;; *) echo 'Unknown argument'; exit 2;; esac; done
[[ "$run_id" =~ ^[a-z][a-z0-9_]{0,40}$ ]] || { echo 'Use --run-id lowercase_id'; exit 2; }
export RELEX_RUN_ID="$run_id"
export RELEX_PYTHON="${RELEX_PYTHON:-.venv-c/bin/python}"
export PATH="/mnt/relex-kai/.tools/node-v22.14.0-linux-x64/bin:$PATH"
export PLAYWRIGHT_BROWSERS_PATH="${PLAYWRIGHT_BROWSERS_PATH:-/mnt/relex-kai/.tools/browsers}"
"$RELEX_PYTHON" scripts/product/run-live.py
