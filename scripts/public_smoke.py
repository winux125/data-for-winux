"""Exercise the actual public upload/poll API. Saves full evidence privately, prints summaries only."""
import argparse
import base64
import gzip
import http.client
import os
import json
import time
import urllib.error
import urllib.request
import uuid
import sys
from pathlib import Path


def run(base, key, video):
    boundary = uuid.uuid4().hex
    body = (f'--{boundary}\r\nContent-Disposition: form-data; name="file"; filename="clip.mov"\r\n'
            'Content-Type: video/quicktime\r\n\r\n').encode() + video.read_bytes() + f'\r\n--{boundary}--\r\n'.encode()
    started = time.monotonic()
    request = urllib.request.Request(base + '/api/v1/analyze', data=body,
        headers={'X-API-Key': key, 'Content-Type': f'multipart/form-data; boundary={boundary}'})
    with urllib.request.urlopen(request, timeout=90) as response:
        assert response.status == 202
        job = json.load(response)
    print(json.dumps({'video': video.name, 'job_id': job['job_id'], 'status': 'submitted'}), flush=True)
    previous = None
    retries = []
    while time.monotonic() - started < 300:
        request = urllib.request.Request(base + '/api/v1/jobs/' + job['job_id'],
            headers={'X-API-Key': key, 'Accept-Encoding': 'gzip'})
        try:
            with urllib.request.urlopen(request, timeout=min(20,max(1,300-(time.monotonic()-started)))) as response:
                assert response.status == 200
                content=response.read()
                if response.headers.get('Content-Encoding')=='gzip':content=gzip.decompress(content)
                result=json.loads(content)
        except urllib.error.HTTPError as exc:
            if exc.code < 500:raise
            retries.append('HTTP_'+str(exc.code))
            time.sleep(2)
            continue
        except (urllib.error.URLError, TimeoutError, http.client.HTTPException, ConnectionError) as exc:
            retries.append(type(exc).__name__)
            time.sleep(2)
            continue
        stage = result.get('stage', result['status'])
        if stage != previous:
            print(json.dumps({'video': video.name, 'stage': stage, 'elapsed': round(time.monotonic()-started, 1)}), flush=True)
            previous = stage
        if result['status'] in ('done', 'failed'):
            result['client_elapsed_sec'] = round(time.monotonic() - started, 3)
            result['poll_retries'] = retries
            assert result['client_elapsed_sec'] <= 300, 'Client deadline exceeded'
            if result['status'] == 'done':
                assert result['verdict'] in ('violation', 'no_violation')
                assert bool(result['violations']) == (result['verdict'] == 'violation')
                for event in result['violations']:
                    assert isinstance(event['timecode_sec'], (int, float))
                    assert 1 <= len(event['evidence_frames']) <= 3
                    for frame in event['evidence_frames']:
                        assert base64.b64decode(frame['image_base64'], validate=True).startswith(b'\xff\xd8')
            return result
        time.sleep(2)
    raise TimeoutError('Public request exceeded 300 seconds; retry GET using the printed job_id')


if __name__ == '__main__':
    parser = argparse.ArgumentParser()
    parser.add_argument('videos', nargs='+', type=Path)
    parser.add_argument('--base', default=os.environ.get('FORTE_API_URL','https://154.54.100.194.sslip.io'))
    parser.add_argument('--key-file', type=Path, default=Path('secrets/service.env'))
    parser.add_argument('--output', type=Path, default=Path('data/public-smoke'))
    args = parser.parse_args()
    entries = dict(line.split('=', 1) for line in args.key_file.read_text().splitlines()
                   if line.strip() and not line.lstrip().startswith('#') and '=' in line)
    key = entries['FORTE_API_KEY'].strip().strip('\"').strip("'")
    args.output.mkdir(parents=True, exist_ok=True)
    failed=False
    for video in args.videos:
        result = run(args.base.rstrip('/'), key, video)
        (args.output / (video.stem + '.json')).write_text(json.dumps(result, ensure_ascii=False), encoding='utf-8')
        print(json.dumps({'video': video.name, 'status': result['status'], 'verdict': result.get('verdict'),
                          'events': len(result.get('violations', [])), 'elapsed': result['client_elapsed_sec'],
                          'error': result.get('error')}), flush=True)
        failed |= result['status'] != 'done'
    sys.exit(1 if failed else 0)
