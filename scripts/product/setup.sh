#!/usr/bin/env bash
set -euo pipefail
cd "$(dirname "$0")/../.."
PYTHON="${RELEX_PYTHON:-python3}"
"$PYTHON" -m venv .venv-product
.venv-product/bin/python -m pip install -e './backend[evidence,intelligence,product,test]'
cd frontend
npm ci
npm run generate
npm run build
