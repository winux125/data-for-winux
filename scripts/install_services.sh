#!/usr/bin/env bash
set -euo pipefail
ROOT="$(cd -- "$(dirname -- "${BASH_SOURCE[0]}")/.." && pwd)"
cd "$ROOT"
: "${FORTE_PUBLIC_HOST:?Set FORTE_PUBLIC_HOST to this servers DNS hostname (without https://)}"
export HF_HOME="${HF_HOME:-$ROOT/models/hf-cache}"
.venv/bin/python scripts/verify_runtime.py --models --cuda
mkdir -p secrets data
chmod 700 secrets data
if [ ! -f secrets/service.env ]; then
    (umask 077; .venv/bin/python -c 'import secrets; print("FORTE_API_KEY="+secrets.token_urlsafe(36))' > secrets/service.env)
fi
chmod 600 secrets/service.env
.venv/bin/python scripts/configure_browser.py --api-origin "https://$FORTE_PUBLIC_HOST" --site-origin "${FORTE_SITE_ORIGIN:-https://$FORTE_PUBLIC_HOST}"
.venv/bin/python scripts/render_deployment.py --root "$ROOT" --user "$(id -un)" --host "$FORTE_PUBLIC_HOST" --hf-home "$HF_HOME"
# Build and validate before changing any running service.
docker build -f deploy/Dockerfile.frontend -t forte-vision:deployment forte-vision
if [ ! -x /usr/local/bin/caddy ]; then
    temporary_caddy="$(mktemp)"
    trap 'rm -f "$temporary_caddy"' EXIT
    curl --fail --location 'https://caddyserver.com/api/download?os=linux&arch=amd64' -o "$temporary_caddy"
    sudo install -m 755 "$temporary_caddy" /usr/local/bin/caddy
fi
/usr/local/bin/caddy validate --config "$ROOT/data/deploy/Caddyfile" --adapter caddyfile
for unit in forte-api forte-worker forte-frontend caddy; do
    sudo install -m 644 "data/deploy/$unit.service" "/etc/systemd/system/$unit.service"
done
sudo systemctl daemon-reload
sudo systemctl enable forte-api forte-worker forte-frontend caddy
sudo systemctl restart forte-api forte-worker forte-frontend caddy
