#!/usr/bin/env bash
set -Eeuo pipefail
ROOT=$(cd -- "$(dirname -- "${BASH_SOURCE[0]}")/../.." && pwd)
cd "$ROOT"
[[ $(id -u) == 0 ]] || { echo 'Run as root.' >&2; exit 1; }

systemctl stop relex-web.service relex-worker.service relex-migrate.service relex-qdrant.service relex-postgres.service 2>/dev/null || true
bash scripts/product/start.sh --prepare-only
# Hand the owned stores from the foreground launcher to systemd without two
# processes competing for the same data directory and ports.
pg_ctl="$ROOT/.tools/pg/usr/lib/postgresql/18/bin/pg_ctl"
pg_data="$ROOT/.runtime/c-postgres/data"
if [[ -x $pg_ctl && -f $pg_data/postmaster.pid ]]; then
    pg_owner=$(stat -c %U "$pg_data")
    if [[ $(id -un) == "$pg_owner" ]]; then "$pg_ctl" -D "$pg_data" stop -m fast -w
    else runuser -u "$pg_owner" -- "$pg_ctl" -D "$pg_data" stop -m fast -w
    fi
fi
qdrant_pid=$(ss -ltnp 'sport = :16333' 2>/dev/null | sed -n 's/.*pid=\([0-9][0-9]*\).*/\1/p' | head -1)
if [[ -n $qdrant_pid ]]; then
    kill -TERM "$qdrant_pid"
    for _ in {1..30}; do kill -0 "$qdrant_pid" 2>/dev/null || break; sleep 1; done
    kill -0 "$qdrant_pid" 2>/dev/null && { echo 'Qdrant did not stop cleanly.' >&2; exit 1; }
fi
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
systemctl enable --now relex.target
echo 'Installed and started relex.target.'
