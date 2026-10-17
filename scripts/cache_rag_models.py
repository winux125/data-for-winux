"""Cache exact public models from the unmodified RAG config before offline startup."""
import json
from pathlib import Path
from huggingface_hub import snapshot_download, hf_hub_download

root = Path(__file__).resolve().parents[1]
config = json.loads((root/'ForteBank-Legal-RAG-2026-10-18/configs/cuda.json').read_text())
for key in ('embedder', 'generator'):
    model = config[key]
    snapshot_download(model['model_id'], revision=model['revision'],
                      ignore_patterns=['*.bin', '*.onnx', 'onnx/*', '*.ot'])
    if key == 'embedder':
        hf_hub_download(model['model_id'], 'pytorch_model.bin', revision=model['revision'])
    print('Cached', model['model_id'], model['revision'], flush=True)
