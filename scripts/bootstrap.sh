#!/usr/bin/env bash
set -euo pipefail
cd /home/shadeform/forte-service
UV=/home/shadeform/.local/bin/uv
if [ ! -x "$UV" ]; then
    curl -LsSf https://astral.sh/uv/install.sh | sh
fi
sudo mkdir -p /ephemeral/forte-service-models/hf-cache
sudo chown -R shadeform:shadeform /ephemeral/forte-service-models
$UV venv --python 3.12 .venv
$UV pip install --python .venv/bin/python torch==2.9.1 torchvision==0.24.1 --index-url https://download.pytorch.org/whl/cu126
$UV pip install --python .venv/bin/python -r requirements.txt
if [ -n "${JEPA_ARCHIVE:-}" ]; then
    .venv/bin/python scripts/install_detector.py --archive "$JEPA_ARCHIVE"
else
    .venv/bin/python scripts/install_detector.py
fi
.venv/bin/python scripts/download_models.py
HF_HOME=/ephemeral/forte-service-models/hf-cache .venv/bin/python scripts/cache_rag_models.py
