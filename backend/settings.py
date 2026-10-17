import os
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
DATA = Path(os.environ.get('FORTE_DATA_DIR', ROOT / 'data'))
DATA.mkdir(parents=True, exist_ok=True)
UPLOADS = DATA / 'uploads'
UPLOADS.mkdir(exist_ok=True)
DB = DATA / 'jobs.sqlite3'
MAX_BYTES = int(os.environ.get('FORTE_MAX_UPLOAD_BYTES', str(10 * 1024 ** 3)))
MIN_FREE_BYTES = 2 * MAX_BYTES + 1024 ** 3
DEADLINE = 285
RETENTION_HOURS = int(os.environ.get('FORTE_RETENTION_HOURS', '24'))


def api_key():
    value = os.environ.get('FORTE_API_KEY', '')
    if len(value) < 24:
        raise RuntimeError('FORTE_API_KEY must contain at least 24 characters')
    return value
