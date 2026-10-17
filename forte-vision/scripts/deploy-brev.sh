#!/usr/bin/env bash
set -euo pipefail
cd "$(dirname "${BASH_SOURCE[0]}")/.."
command -v docker >/dev/null || { echo "Docker is required on the Brev instance." >&2; exit 1; }
docker compose version >/dev/null
if [[ ! -f deploy/brev/runtime.env ]]; then
  echo "Copy deploy/brev/runtime.env.example to deploy/brev/runtime.env and configure it first." >&2
  exit 1
fi
docker compose --project-name forte-vision --env-file deploy/brev/runtime.env -f deploy/brev/compose.yaml up -d --build --wait --wait-timeout 180
docker compose --project-name forte-vision --env-file deploy/brev/runtime.env -f deploy/brev/compose.yaml ps
