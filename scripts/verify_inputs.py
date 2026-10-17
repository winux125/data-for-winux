"""Verify unpacked JEPA/RAG byte-for-byte against the supplied archives. Read only."""
import hashlib
import json
from pathlib import Path
import zipfile

root = Path(__file__).resolve().parents[1]
reports = []
for name in ['JEPA-FULL.zip', 'ForteBank-Legal-RAG-2026-10-18.zip']:
    mismatches, count = [], 0
    with zipfile.ZipFile(root / name) as archive:
        for entry in archive.infolist():
            if entry.is_dir():
                continue
            target = (root / entry.filename).resolve()
            if not target.is_relative_to(root):
                raise ValueError('Invalid archive path')
            count += 1
            if not target.is_file():
                mismatches.append(entry.filename)
                continue
            with archive.open(entry) as stream:
                expected = hashlib.file_digest(stream, 'sha256').hexdigest()
            with target.open('rb') as stream:
                actual = hashlib.file_digest(stream, 'sha256').hexdigest()
            if actual != expected:
                mismatches.append(entry.filename)
    reports.append({'archive': name, 'verified_files': count, 'unchanged': not mismatches,
                    'mismatches': mismatches})
destination = root / 'data' / 'input-integrity.json'
destination.parent.mkdir(exist_ok=True)
destination.write_text(json.dumps(reports, indent=2), encoding='utf-8')
print(json.dumps(reports))
raise SystemExit(0 if all(r['unchanged'] for r in reports) else 1)
