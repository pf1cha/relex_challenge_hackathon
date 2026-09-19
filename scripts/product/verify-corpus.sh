#!/usr/bin/env bash
set -Eeuo pipefail

ROOT=$(cd -- "$(dirname -- "${BASH_SOURCE[0]}")/../.." && pwd)
cd "$ROOT"

if [[ -z ${RELEX_PYTHON:-} ]]; then
  for candidate in "$ROOT/.tools/miniforge3/envs/relex/bin/python" "$ROOT/.venv/bin/python"; do
    if [[ -x $candidate ]]; then
      RELEX_PYTHON=$candidate
      break
    fi
  done
fi
export RELEX_PYTHON=${RELEX_PYTHON:-python3}
command -v "$RELEX_PYTHON" >/dev/null || {
  echo "No usable Python found. Set RELEX_PYTHON or run scripts/product/setup.sh." >&2
  exit 1
}

[[ -f .env ]] || {
  echo "Missing .env in $ROOT." >&2
  exit 1
}

# The provider base is joined with /chat/completions by the client. Keep an
# explicit caller override, but default to the configured OpenAI-compatible v1
# route so the provider homepage is never mistaken for a JSON response.
export RELEX_MODEL_BASE_URL=${RELEX_MODEL_BASE_URL:-https://sub.callai.one/v1}
export PYTHONPATH="$ROOT/backend${PYTHONPATH:+:$PYTHONPATH}"

exec "$RELEX_PYTHON" scripts/product/verify-corpus.py "$@"
