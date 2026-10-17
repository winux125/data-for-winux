#!/usr/bin/env bash
set -euo pipefail
cd /home/shadeform/forte-service
mkdir -p secrets data
sudo chown -R shadeform:shadeform secrets data
chmod 700 secrets data
if [ ! -f secrets/service.env ]; then
    .venv/bin/python -c 'import secrets;print("FORTE_API_KEY="+secrets.token_urlsafe(36))' > secrets/service.env
    chmod 600 secrets/service.env
fi
sudo chown shadeform:shadeform secrets/service.env
sudo cp deploy/forte-api.service deploy/forte-worker.service /etc/systemd/system/
docker build -f forte-vision/deploy/brev/Dockerfile -t forte-vision:deployment forte-vision
sudo cp deploy/forte-frontend.service /etc/systemd/system/
sudo systemctl daemon-reload
sudo systemctl enable --now forte-api forte-worker forte-frontend
if [ ! -x /usr/local/bin/caddy ]; then
    curl --fail --location 'https://caddyserver.com/api/download?os=linux&arch=amd64' -o /tmp/forte-caddy
    sudo install -m 755 /tmp/forte-caddy /usr/local/bin/caddy
fi
sudo cp deploy/caddy.service /etc/systemd/system/caddy.service
sudo systemctl daemon-reload
sudo systemctl enable --now caddy
