import base64
import io
import time

import pytest
from fastapi.testclient import TestClient
from PIL import Image

from backend import api, store

KEY = 'test-key-long-enough-for-security-123'


@pytest.fixture
def client(tmp_path, monkeypatch):
    monkeypatch.setenv('FORTE_API_KEY', KEY)
    monkeypatch.setattr(store, 'DB', tmp_path / 'jobs.db')
    uploads = tmp_path / 'uploads'
    uploads.mkdir()
    monkeypatch.setattr(api, 'UPLOADS', uploads)
    monkeypatch.setattr(store, 'UPLOADS', uploads)
    with TestClient(api.app) as client:
        store.worker_state(True, 'ready')
        yield client


def upload(client, filename='clip.mov', data=b'video'):
    return client.post('/api/v1/analyze', headers={'X-API-Key': KEY}, files={'file': (filename, data)})


def test_auth_required_for_submission_and_results(client):
    assert client.post('/api/v1/analyze', files={'file': ('clip.mov', b'x')}).status_code == 401
    assert client.get('/api/v1/jobs/unknown').status_code == 401
    assert client.get('/api/v1/rules').status_code == 401
    assert client.get('/healthz').status_code == 200


def test_job_schema_and_actual_jpeg(client):
    response = upload(client)
    assert response.status_code == 202
    job_id = response.json()['job_id']
    assert store.claim()['id'] == job_id
    response = client.get('/api/v1/jobs/' + job_id, headers={'X-API-Key': KEY})
    assert response.json()['status'] == 'processing'
    stream = io.BytesIO()
    Image.new('RGB', (16, 16), '#086c6e').save(stream, 'JPEG')
    frame = {'timestamp_sec': 1.25, 'image_base64': base64.b64encode(stream.getvalue()).decode()}
    result = {'verdict': 'violation', 'violations': [{'type': 'Уход кассира', 'timecode_sec': 1.25,
              'description': 'Наблюдаемое действие', 'evidence_frames': [frame]}]}
    store.complete(job_id, result)
    body = client.get('/api/v1/jobs/' + job_id, headers={'X-API-Key': KEY}).json()
    assert body['status'] == 'done' and body['verdict'] == 'violation'
    image = Image.open(io.BytesIO(base64.b64decode(body['violations'][0]['evidence_frames'][0]['image_base64'])))
    assert image.format == 'JPEG'


def test_no_violation_has_empty_events(client):
    job_id = upload(client).json()['job_id']
    store.complete(job_id, {'verdict': 'no_violation', 'violations': []})
    body = client.get('/api/v1/jobs/' + job_id, headers={'X-API-Key': KEY}).json()
    assert body['status'] == 'done' and body['violations'] == []


def test_rejects_empty_unsupported_and_oversized_uploads(client, monkeypatch):
    assert upload(client, data=b'').status_code == 400
    assert upload(client, filename='file.txt').status_code == 415
    monkeypatch.setattr(api, 'MAX_BYTES', 4)
    assert upload(client, data=b'12345').status_code == 413
    assert list(api.UPLOADS.iterdir()) == []


def test_models_loading_and_more_than_two_jobs_are_durably_accepted(client):
    store.worker_state(False, 'loading')
    assert upload(client).status_code == 202
    store.worker_state(True, 'ready')
    assert upload(client).status_code == 202
    assert upload(client).status_code == 202
    assert upload(client).status_code == 202
    assert len(list(api.UPLOADS.iterdir())) == 4


def test_deadline_cannot_be_overwritten_with_clean_verdict(client):
    job_id = upload(client).json()['job_id']
    with store.connect() as db:
        db.execute('UPDATE jobs SET created=? WHERE id=?', (time.time() - 300, job_id))
    assert store.get(job_id)['status'] == 'failed'
    store.complete(job_id, {'verdict': 'no_violation', 'violations': []})
    body = client.get('/api/v1/jobs/' + job_id, headers={'X-API-Key': KEY}).json()
    assert body['status'] == 'failed' and body['error'] == 'processing_timeout'
    assert 'verdict' not in body
    store.cleanup()
    assert not (api.UPLOADS / (job_id + '.mov')).exists()


def test_restart_does_not_drop_queued_job(client):
    first, second = upload(client).json()['job_id'], upload(client).json()['job_id']
    store.claim()
    store.recover()
    assert store.get(first)['stage'] == 'queued'
    assert store.get(first)['error'] is None
    assert store.get(second)['stage'] == 'queued'


def test_filenames_not_used_as_storage_paths(client):
    body = upload(client, filename='../../secret.mov').json()
    assert (api.UPLOADS / (body['job_id'] + '.mov')).is_file()
    assert client.get('/api/v1/jobs/missing', headers={'X-API-Key': KEY}).status_code == 404


def test_browser_session_cannot_access_jury_routes_or_another_browser_job(client):
    assert client.post('/api/browser/session').status_code == 403
    first = client.post('/api/browser/session', headers={'Origin':'http://testserver'}).json()['token']
    second = client.post('/api/browser/session', headers={'Origin':'http://testserver'}).json()['token']
    headers = {'X-API-Key':first}
    assert client.get('/api/v1/rules',headers=headers).status_code == 401
    body = client.post('/api/browser/analyze',headers=headers,files={'file':('clip.mov',b'video')}).json()
    endpoint = '/api/browser/jobs/'+body['job_id']
    assert client.get(endpoint,headers={'X-API-Key':second}).status_code == 404
    assert client.get(endpoint,headers={'X-API-Key':KEY}).status_code == 401
    assert client.get(endpoint,headers=headers).status_code == 200
    with store.connect() as db:
        db.execute('UPDATE jobs SET created=? WHERE id=?',(time.time()-600,body['job_id']))
    assert store.get(body['job_id'])['status'] == 'processing'
    assert store.claim()['id'] == body['job_id']


def test_browser_config_does_not_expose_jury_key(client):
    body=client.get('/api/browser/config').json()
    assert body['max_upload_bytes']==10*1024**3
    assert KEY not in str(body)
