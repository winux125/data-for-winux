"""Development-only dataset inventory; never imported by the inference service."""
import hashlib
import json
import re
from collections import defaultdict
from pathlib import Path

import openpyxl

root = Path(__file__).resolve().parents[1]
rows = list(openpyxl.load_workbook(root / 'open/open_labels.xlsx', read_only=True, data_only=True).active.values)
files = list((root / 'open/videos').glob('*.mov'))
by_number = {int(re.search(r'\d+', p.stem).group()): p for p in files}
records, missing = [], []
groups = defaultdict(list)
for name, point, label in rows[1:]:
    if not name:
        continue
    number = int(re.search(r'\d+', name).group())
    path = by_number.get(number)
    if not path:
        missing.append(name)
        continue
    digest = hashlib.file_digest(path.open('rb'), 'sha256').hexdigest()
    positive = label.strip().casefold() == 'нарушение'
    record = {'number': number, 'file': path.name, 'positive': positive, 'annotated_time': point,
              'sha256': digest, 'bytes': path.stat().st_size}
    records.append(record)
    groups[digest].append(record)
unique = [g[0] for g in groups.values()]
result = {'files': len(files), 'label_rows': len(rows)-1, 'unique_videos': len(unique),
          'unique_positive': sum(x['positive'] for x in unique), 'missing_files': missing,
          'duplicate_groups': [[x['number'] for x in g] for g in groups.values() if len(g)>1],
          'conflicting_duplicate_labels': [[x['number'] for x in g] for g in groups.values()
                                             if len({x['positive'] for x in g}) > 1],
          'records': records}
(root / 'data').mkdir(exist_ok=True)
(root / 'data/dataset_audit.json').write_text(json.dumps(result, ensure_ascii=False, indent=2), encoding='utf-8')
print(json.dumps({k:v for k,v in result.items() if k != 'records'}, ensure_ascii=True))
