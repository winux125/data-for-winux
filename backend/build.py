"""Fingerprint executable source, model identity and non-secret configuration."""
import hashlib
import json
from pathlib import Path


def build_id(root):
    root = Path(root)
    files = []
    for directory in ('backend', 'legal_rag'):
        files.extend(p for p in (root / directory).rglob('*.py')
                     if 'tests' not in p.parts and '__pycache__' not in p.parts)
    files.extend((root / 'config').glob('*.json'))
    files.extend((root / 'legal_rag/data').glob('*.json'))
    settings = json.loads((root / 'config/detector.json').read_text(encoding='utf-8'))
    files.append(root / settings['package_dir'] / 'model.json')
    digest = hashlib.sha256()
    for file in sorted(files):
        digest.update(file.relative_to(root).as_posix().encode())
        digest.update(b'\0')
        # Git normalizes service text on checkout; Windows and Linux must agree.
        digest.update(file.read_bytes().replace(b'\r\n', b'\n'))
        digest.update(b'\0')
    return digest.hexdigest()[:16]
