"""Anonymous, job-scoped browser access. The jury key never leaves the server."""
import base64
import hashlib
import hmac
import json
import time
import uuid

from fastapi import Header, HTTPException, Request
from .settings import api_key


def issue_session():
    payload = json.dumps({'id': uuid.uuid4().hex, 'exp': int(time.time()) + 86400}, separators=(',', ':')).encode()
    data = base64.urlsafe_b64encode(payload).decode().rstrip('=')
    signature = hmac.new(api_key().encode(), ('browser:' + data).encode(), hashlib.sha256).hexdigest()
    return {'token': data + '.' + signature, 'expires_at': json.loads(payload)['exp']}


def browser_client(x_api_key: str = Header(default='', alias='X-API-Key')):
    try:
        data, signature = x_api_key.split('.')
        expected = hmac.new(api_key().encode(), ('browser:' + data).encode(), hashlib.sha256).hexdigest()
        if not hmac.compare_digest(signature, expected):
            raise ValueError()
        payload = json.loads(base64.urlsafe_b64decode(data + '=' * (-len(data) % 4)))
        if payload['exp'] < time.time() or len(payload['id']) != 32:
            raise ValueError()
        return payload['id']
    except (ValueError, KeyError, TypeError):
        raise HTTPException(401, 'Browser session expired; reload the page') from None


def check_origin(request: Request):
    import os
    origin = request.headers.get('origin')
    allowed = set(x.strip() for x in os.environ.get('FORTE_CORS_ORIGINS', '').split(',') if x.strip())
    allowed.add(str(request.base_url).rstrip('/'))
    if not origin or origin not in allowed:
        raise HTTPException(403, 'Browser origin is not allowed')
