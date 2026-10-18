#!/usr/bin/env bash
set -euo pipefail
ROOT="$(cd -- "$(dirname -- "${BASH_SOURCE[0]}")/.." && pwd)"
cd "$ROOT"
UV="${UV_BIN:-$(command -v uv || true)}"
if [ -z "$UV" ]; then
    printf '%s\n' 'Install uv first: https://docs.astral.sh/uv/getting-started/installation/' >&2
    exit 1
fi
export HF_HOME="${HF_HOME:-$ROOT/models/hf-cache}"
mkdir -p "$HF_HOME" models data
"$UV" venv --python 3.12 .venv
"$UV" pip install --python .venv/bin/python torch==2.9.1 torchvision==0.24.1 --index-url https://download.pytorch.org/whl/cu126
"$UV" pip install --python .venv/bin/python -r requirements.txt
if [ -n "${JEPA_ARCHIVE:-}" ]; then
    .venv/bin/python scripts/install_detector.py --archive "$JEPA_ARCHIVE"
else
    .venv/bin/python scripts/install_detector.py
fi
.venv/bin/python scripts/download_models.py
.venv/bin/python scripts/cache_rag_models.py
.venv/bin/python scripts/verify_runtime.py --models --cuda
.venv/bin/python -m pytest tests legal_rag/tests -q
