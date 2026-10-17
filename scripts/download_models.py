from pathlib import Path
from huggingface_hub import snapshot_download, hf_hub_download

root = Path(__file__).resolve().parents[1] / 'models'
for name, revision, directory in [
    ('Qwen/Qwen3-VL-8B-Instruct', '0c351dd01ed87e9c1b53cbc748cba10e6187ff3b', 'qwen3-vl-8b'),
    ('BAAI/bge-m3', '5617a9f61b028005a4858fdac845db406aefb181', 'bge-m3'),
]:
    snapshot_download(name, revision=revision, local_dir=root / directory,
                      ignore_patterns=['*.bin', '*.onnx', '*.ot', 'onnx/*'])
    print('Downloaded', name, revision, flush=True)
    if name == 'BAAI/bge-m3':
        hf_hub_download(name, 'pytorch_model.bin', revision=revision, local_dir=root / directory)
