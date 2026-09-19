#!/usr/bin/env bash
set -euo pipefail
cd "$(dirname "$0")/../.."
"${RELEX_PYTHON:-.venv-c/bin/python}" scripts/product/export-openapi.py
cd frontend
npm run generate
