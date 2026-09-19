#!/usr/bin/env bash
set -euo pipefail
cd "$(dirname "$0")/../.."
root="$PWD/scripts/intelligence/runtime"
mkdir -p "$root/config" "$root/storage"
if [[ ! -x "$root/qdrant" ]]; then
  curl -fsSL https://github.com/qdrant/qdrant/releases/download/v1.14.1/qdrant-x86_64-unknown-linux-musl.tar.gz -o "$root/qdrant.tar.gz"
  tar -xzf "$root/qdrant.tar.gz" -C "$root"
fi
cat > "$root/config/local.yaml" <<YAML
storage:
  storage_path: $root/storage
service:
  host: 127.0.0.1
  http_port: ${RELEX_QDRANT_HTTP_PORT:-16333}
  grpc_port: ${RELEX_QDRANT_GRPC_PORT:-16334}
telemetry_disabled: true
YAML
exec "$root/qdrant" --config-path "$root/config/local.yaml"
