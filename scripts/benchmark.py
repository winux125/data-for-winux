"""Public development benchmark. Labels are never sent to the service or used for fitting."""
import json
import re
import time
import urllib.request
import urllib.error
from pathlib import Path

from public_smoke import run

root = Path(__file__).resolve().parents[1]
audit = json.loads((root / 'data/dataset_audit.json').read_text(encoding='utf-8'))
key = (root / 'secrets/service.env').read_text().strip().split('=', 1)[1]
output = root / 'data/benchmark'
output.mkdir(exist_ok=True)
seen = set()
summary = []
for attempt in range(90):
    try:
        urllib.request.urlopen('https://185.216.22.24.sslip.io/readyz', timeout=10).close()
        break
    except urllib.error.HTTPError:
        time.sleep(2)
else:
    raise RuntimeError('Models did not become ready')
for record in audit['records']:
    if record['sha256'] in seen:
        continue
    seen.add(record['sha256'])
    path = root / 'open/videos' / record['file']
    destination = output / (str(record['number']) + '.json')
    try:
        result = run('https://185.216.22.24.sslip.io', key, path)
        destination.write_text(json.dumps(result, ensure_ascii=False), encoding='utf-8')
        actual = result.get('verdict') == 'violation' if result['status'] == 'done' else None
        item = {'number': record['number'], 'expected_positive': record['positive'], 'predicted_positive': actual,
                'status': result['status'], 'correct': actual == record['positive'],
                'elapsed_sec': result['client_elapsed_sec'], 'events': len(result.get('violations', []))}
        if record['annotated_time'] and result.get('violations'):
            points = [float(x.replace(',', '.')) for x in re.findall(r'\d+(?:[.,]\d+)?', str(record['annotated_time']))]
            item['nearest_point_error_sec'] = min(abs(v['timecode_sec']-p) for v in result['violations'] for p in points)
    except Exception as exc:
        item = {'number': record['number'], 'status': 'client_error', 'error_type': type(exc).__name__, 'correct': False}
    summary.append(item)
    (output / 'summary.json').write_text(json.dumps(summary, indent=2), encoding='utf-8')
    print(json.dumps({'completed': len(summary), **item}), flush=True)
