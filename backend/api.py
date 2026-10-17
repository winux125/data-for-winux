import hmac
import json
import os
import uuid
import shutil
from contextlib import asynccontextmanager
from pathlib import Path

from fastapi import Depends, FastAPI, File, Header, HTTPException, UploadFile, Request
from fastapi.middleware.cors import CORSMiddleware
from fastapi.responses import JSONResponse

from . import store
from .settings import MAX_BYTES, MIN_FREE_BYTES, ROOT, UPLOADS, api_key
from .browser import browser_client, check_origin, issue_session


@asynccontextmanager
async def lifespan(app):
    api_key()
    store.init()
    yield


app = FastAPI(title='Forte Video Audit API', version='1.0.0', lifespan=lifespan)
origins = [x.strip() for x in os.environ.get('FORTE_CORS_ORIGINS', '').split(',') if x.strip()]
if origins:
    app.add_middleware(CORSMiddleware, allow_origins=origins, allow_methods=['GET', 'POST'],
                       allow_headers=['X-API-Key', 'Content-Type'], allow_credentials=False)


def authorized(x_api_key: str = Header(default='', alias='X-API-Key')):
    if not hmac.compare_digest(x_api_key.encode(), api_key().encode()):
        raise HTTPException(401, 'Invalid or missing X-API-Key')


@app.middleware('http')
async def security_headers(request, call_next):
    length = request.headers.get('content-length', '')
    if request.url.path in ('/api/v1/analyze', '/api/browser/analyze') and length.isdecimal() and int(length) > MAX_BYTES + 1024 * 1024:
        return JSONResponse({'detail': 'Video exceeds upload limit'}, status_code=413)
    response = await call_next(request)
    response.headers['X-Content-Type-Options'] = 'nosniff'
    response.headers['Referrer-Policy'] = 'no-referrer'
    response.headers['Cache-Control'] = 'no-store'
    return response


@app.get('/healthz')
def health():
    return {'status': 'ok'}


@app.get('/readyz')
def ready():
    value = store.readiness()
    return JSONResponse({'status': 'ready' if value else 'loading'}, status_code=200 if value else 503)


@app.post('/api/v1/analyze', dependencies=[Depends(authorized)], status_code=202)
async def analyze(file: UploadFile = File(...)):
    return await enqueue(file)


async def enqueue(file, client_id=None):
    if Path(file.filename or '').suffix.lower() not in {'.mov', '.mp4'}:
        raise HTTPException(415, 'Upload a .mov or .mp4 video')
    # Admission is independent of model warm-up. Jobs survive worker restarts.
    if shutil.disk_usage(UPLOADS).free < MIN_FREE_BYTES:
        raise HTTPException(507, 'Insufficient upload storage')
    job_id = uuid.uuid4().hex[:16]
    path = UPLOADS / (job_id + '.mov')
    try:
        size = 0
        with path.open('xb') as stream:
            while chunk := await file.read(1024 * 1024):
                size += len(chunk)
                if size > MAX_BYTES:
                    raise HTTPException(413, 'Video exceeds upload limit')
                stream.write(chunk)
        if not size:
            raise HTTPException(400, 'Video is empty')
        store.create(job_id, client_id)
    except BaseException:
        path.unlink(missing_ok=True)
        raise
    finally:
        await file.close()
    return {'job_id': job_id, 'status': 'processing'}


@app.get('/api/v1/jobs/{job_id}', dependencies=[Depends(authorized)])
def job(job_id: str):
    row = store.get(job_id)
    if not row:
        raise HTTPException(404, 'Job not found')
    if row['status'] == 'done':
        return {'job_id': job_id, 'status': 'done', **json.loads(row['result'])}
    result = {'job_id': job_id, 'status': row['status'], 'stage': row['stage']}
    if row['stage'] == 'queued':
        result['queue_position'] = store.queue_position(job_id)
    if row['error']:
        result['error'] = row['error']
    return result


@app.get('/api/v1/rules', dependencies=[Depends(authorized)])
def rules():
    return json.loads((ROOT / 'config' / 'rules_public.json').read_text(encoding='utf-8'))


@app.get('/api/browser/config')
def browser_config():
    return {'base_url': os.environ.get('FORTE_BROWSER_API_ORIGIN', ''), 'max_upload_bytes': MAX_BYTES}


@app.post('/api/browser/session', dependencies=[Depends(check_origin)])
def browser_session():
    return issue_session()


@app.post('/api/browser/analyze', status_code=202)
async def browser_analyze(client_id: str = Depends(browser_client), file: UploadFile = File(...)):
    return await enqueue(file, client_id)


@app.get('/api/browser/jobs/{job_id}')
def browser_job(job_id: str, client_id: str = Depends(browser_client)):
    row = store.get(job_id)
    if not row or row['client_id'] != client_id:
        raise HTTPException(404, 'Job not found')
    return job(job_id)


