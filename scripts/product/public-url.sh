#!/usr/bin/env bash
# Control the public HTTPS endpoint without stopping the Relex application.
set -Eeuo pipefail

ROOT=$(cd -- "$(dirname -- "${BASH_SOURCE[0]}")/../.." && pwd)
readonly CADDY_SERVICE=${CADDY_SERVICE:-caddy.service}
readonly CADDYFILE=${CADDYFILE:-/etc/caddy/Caddyfile}

usage() {
  cat <<'HELP'
Usage: bash scripts/product/public-url.sh {start|stop|restart|status}

Controls the system Caddy reverse proxy. Caddy is the public HTTPS layer;
the Relex web/worker services and their data stores are not stopped by this
script. The public hostname and upstream are configured in /etc/caddy/Caddyfile
(repository template: deploy/Caddyfile).
HELP
}

require_root() {
  [[ $(id -u) == 0 ]] || { echo 'Run as root (or use sudo).' >&2; exit 1; }
}

check_config() {
  [[ -r $CADDYFILE ]] || { echo "Missing Caddy config: $CADDYFILE" >&2; exit 1; }
  caddy validate --config "$CADDYFILE" --adapter caddyfile >/dev/null
}

action=${1:-status}
case "$action" in
  start)
    require_root
    check_config
    systemctl start "$CADDY_SERVICE"
    echo "Public URL started: $(sed -n '1s/[[:space:]]*{//p' "$CADDYFILE")"
    ;;
  stop)
    require_root
    systemctl stop "$CADDY_SERVICE"
    echo 'Public URL stopped. Relex services remain running on localhost.'
    ;;
  restart)
    require_root
    check_config
    systemctl restart "$CADDY_SERVICE"
    echo "Public URL restarted: $(sed -n '1s/[[:space:]]*{//p' "$CADDYFILE")"
    ;;
  status)
    systemctl status "$CADDY_SERVICE" --no-pager
    ;;
  -h|--help)
    usage
    ;;
  *)
    echo "Unknown action: $action" >&2
    usage >&2
    exit 2
    ;;
esac
