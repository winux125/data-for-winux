"""Download public weights only, never videos or descriptions."""
from pathlib import Path
from huggingface_hub import snapshot_download

target = Path('/ephemeral/forte-service-models/qwen3-vl-32b')
target.mkdir(parents=True, exist_ok=True)
snapshot_download('Qwen/Qwen3-VL-32B-Instruct',
    revision='0cfaf48183f594c314753d30a4c4974bc75f3ccb', local_dir=target,
    ignore_patterns=['*.bin','*.onnx','*.ot'])
print('32B public weights downloaded', flush=True)
