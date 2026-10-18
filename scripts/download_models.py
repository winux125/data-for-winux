"""Download only the visual observer; RAG models use the shared HF cache."""
import json
from pathlib import Path
from huggingface_hub import snapshot_download

root=Path(__file__).resolve().parents[1]
source=json.loads((root/'config/model-downloads.json').read_text(encoding='utf-8'))['observer']
observer=json.loads((root/'config/observer.json').read_text(encoding='utf-8'))
directory=Path(source['directory'])
if directory.is_absolute() or '..' in directory.parts or directory.parts[0]!='models':
    raise ValueError('Observer directory must be inside models/')
if str(directory).replace('\\','/')!=observer['model_id']:
    raise ValueError('Download and inference observer paths differ')
snapshot_download(source['repository'],revision=source['revision'],local_dir=root/directory,
                  ignore_patterns=['*.bin','*.onnx','*.ot','onnx/*'])
print('Downloaded observer at the pinned revision; RAG weights are cached separately.')
