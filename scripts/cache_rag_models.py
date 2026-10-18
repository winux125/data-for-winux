"""Cache the exact models selected by the service before offline startup."""
import json
from pathlib import Path
from huggingface_hub import snapshot_download, hf_hub_download

root = Path(__file__).resolve().parents[1]
config = json.loads((root/'config/rag-mvp.json').read_text(encoding='utf-8'))
for key in ('embedder', 'generator'):
    model = config[key]
    snapshot_download(model['model_id'], revision=model['revision'],
                      ignore_patterns=['*.bin', '*.onnx', 'onnx/*', '*.ot'])
    if key == 'embedder':
        hf_hub_download(model['model_id'], 'pytorch_model.bin', revision=model['revision'])
    print('Cached', model['model_id'], model['revision'], flush=True)
