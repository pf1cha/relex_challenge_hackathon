#!/usr/bin/env bash
set -Eeuo pipefail
ROOT=$(cd -- "$(dirname -- "${BASH_SOURCE[0]}")/../.." && pwd)
cd "$ROOT"
[[ $(id -u) == 0 ]] || { echo 'Run as root.' >&2; exit 1; }

bash scripts/product/start.sh --prepare-only
install -d -m 0700 /etc/relex
RELEX_ROOT=$ROOT "$ROOT/.tools/miniforge3/envs/relex/bin/python" - <<'PY'
import os, shlex
from pathlib import Path
from dotenv import dotenv_values
root=Path(os.environ["RELEX_ROOT"])
values={k:v for k,v in dotenv_values(root/".env").items() if v is not None}
secret=values.get("RELEX_SESSION_SECRET","")
if not secret:
    line=(root/".runtime/manual/env.sh").read_text().strip()
    secret=shlex.split(line.removeprefix("export RELEX_SESSION_SECRET="))[0]
values.update({
    "RELEX_SESSION_SECRET":secret,
    "RELEX_SECRET":values.get("RELEX_SECRET") or secret,
    "RELEX_DATABASE_URL":values.get("RELEX_DATABASE_URL") or "postgresql://relex_dev@127.0.0.1:15432/postgres",
    "RELEX_DATABASE_SCHEMA":values.get("RELEX_DATABASE_SCHEMA") or "manual_demo",
    "RELEX_QDRANT_URL":values.get("RELEX_QDRANT_URL") or "http://127.0.0.1:16333",
    "RELEX_QDRANT_COLLECTION":values.get("RELEX_QDRANT_COLLECTION") or "manual_demo",
    "RELEX_HOST":"127.0.0.1", "RELEX_PORT":"18080",
})
with open("/etc/relex/relex.env","w") as output:
    for key,value in sorted(values.items()): output.write(f'{key}={shlex.quote(value)}\n')
os.chmod("/etc/relex/relex.env",0o600)
PY
install -m 0644 deploy/systemd/relex*.service deploy/systemd/relex.target /etc/systemd/system/
systemctl daemon-reload
systemctl enable relex.target
echo 'Installed relex.target. Stop the current foreground demo, then run: systemctl start relex.target'
