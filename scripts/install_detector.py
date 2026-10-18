"""Install the owner's detector ZIP unchanged; weights stay out of Git.

Run from an existing service environment after installing requirements.txt.
No package installer, downloads, GPU allocation or service restart is performed.
"""
import argparse
import hashlib
import json
from pathlib import Path, PurePosixPath
import shutil
import zipfile

ROOT = Path(__file__).resolve().parents[1]


def install(archive=None, root=ROOT):
    root = Path(root).resolve()
    config = json.loads((root / 'config/detector.json').read_text(encoding='utf-8'))
    package = (root / config['package_dir']).resolve()
    if not package.is_relative_to(root):
        raise ValueError('Detector path escapes service root')
    if archive:
        with zipfile.ZipFile(archive) as source:
            for info in source.infolist():
                name = PurePosixPath(info.filename)
                if not name.parts or name.parts[0] != 'JEPA-LGBM' or '\\' in info.filename:
                    raise ValueError('Unexpected archive layout')
                rel = Path(*name.parts[1:])
                target = (package / rel).resolve()
                if not target.is_relative_to(package) or info.external_attr >> 16 & 0o170000 == 0o120000:
                    raise ValueError('Unsafe archive member')
                if info.is_dir():
                    continue
                if target.exists():
                    with source.open(info) as incoming:
                        expected = hashlib.file_digest(incoming, 'sha256').hexdigest()
                    with target.open('rb') as existing:
                        if hashlib.file_digest(existing, 'sha256').hexdigest() != expected:
                            raise ValueError('Refusing to replace modified package file: ' + str(rel))
                    continue
                target.parent.mkdir(parents=True, exist_ok=True)
                with source.open(info) as incoming, target.open('wb') as output:
                    shutil.copyfileobj(incoming, output)
    spec = json.loads((package / 'model.json').read_text(encoding='utf-8'))
    if spec['model_id'] != config['model_id']:
        raise ValueError('Detector identity mismatch')
    for name, expected in spec['sha256'].items():
        target = (package / name).resolve()
        if not target.is_relative_to(package):
            raise ValueError('Unsafe manifest path')
        with target.open('rb') as stream:
            if hashlib.file_digest(stream, 'sha256').hexdigest() != expected:
                raise ValueError('Detector checksum mismatch: ' + name)
    return {'model_id': spec['model_id'], 'verified_files': len(spec['sha256']),
            'package_dir': config['package_dir']}


if __name__ == '__main__':
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--archive', type=Path, help='Original JEPA-LGBM-FULL.zip; omit to verify existing files')
    print(json.dumps(install(parser.parse_args().archive)))
