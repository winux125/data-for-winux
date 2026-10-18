"""Build the versioned RAG overlay; never modify the incoming JEPA/RAG packages.

Run from the project root before restarting the idle worker. No network required.
"""
from pathlib import Path
import hashlib
import json
import shutil

root = Path(__file__).resolve().parents[1]
stock = root / 'ForteBank-Legal-RAG-2026-10-18'
patch = root / 'patches/legal-rag-mvp-v1'
release = root / 'releases/legal-rag-mvp-v1'
files = sorted(p for p in patch.rglob('*') if p.is_file() and '__pycache__' not in p.parts)
assert files and (stock / 'legal_rag').is_dir(), 'Missing source package or patch'
if release.exists():
    for file in files:
        target = release / file.relative_to(patch)
        assert target.is_file() and target.read_bytes() == file.read_bytes(), f'Release differs: {target}'
    print('Existing release matches the patch; no files changed.')
else:
    shutil.copytree(stock, release,
                    ignore=shutil.ignore_patterns('__pycache__', '*.pyc', 'build', '*.egg-info'))
    for file in files:
        target = release / file.relative_to(patch)
        target.parent.mkdir(parents=True, exist_ok=True)
        shutil.copy2(file, target)
    manifest = {str(p.relative_to(patch)): hashlib.sha256(p.read_bytes()).hexdigest() for p in files}
    (release / 'MVP_PATCH_MANIFEST.json').write_text(json.dumps(manifest, indent=2), encoding='utf-8')
    print('Created releases/legal-rag-mvp-v1; incoming packages unchanged.')
