import json
import sqlite3
import time
from contextlib import contextmanager

from .settings import DB, DEADLINE, UPLOADS, DATA, RETENTION_HOURS


@contextmanager
def connect():
    db = sqlite3.connect(DB, timeout=20)
    db.row_factory = sqlite3.Row
    try:
        yield db
        db.commit()
    finally:
        db.close()


def init():
    with connect() as db:
        db.execute('PRAGMA journal_mode=WAL')
        db.execute('CREATE TABLE IF NOT EXISTS jobs (id TEXT PRIMARY KEY, created REAL, status TEXT, stage TEXT, result TEXT, error TEXT)')
        db.execute('CREATE TABLE IF NOT EXISTS worker (id INTEGER PRIMARY KEY, ready INTEGER, heartbeat REAL, detail TEXT)')
        columns = {r['name'] for r in db.execute('PRAGMA table_info(jobs)')}
        for name, kind in [('client_id', 'TEXT'), ('started', 'REAL'), ('attempts', 'INTEGER DEFAULT 0')]:
            if name not in columns:
                db.execute(f'ALTER TABLE jobs ADD COLUMN {name} {kind}')


def worker_state(ready, detail):
    with connect() as db:
        db.execute('INSERT OR REPLACE INTO worker VALUES (1,?,?,?)', (int(ready), time.time(), detail))


def readiness():
    with connect() as db:
        row = db.execute('SELECT * FROM worker WHERE id=1').fetchone()
    return bool(row and row['ready'] and time.time() - row['heartbeat'] < 30)


def create(job_id, client_id=None):
    with connect() as db:
        db.execute('BEGIN IMMEDIATE')
        db.execute('INSERT INTO jobs (id,created,status,stage,client_id) VALUES (?,?,?,?,?)',
                   (job_id, time.time(), 'processing', 'queued', client_id))
    return True


def get(job_id):
    with connect() as db:
        row = db.execute('SELECT * FROM jobs WHERE id=?', (job_id,)).fetchone()
        # Browser jobs may wait in the durable queue. Jury jobs retain their
        # mandatory end-to-end deadline; neither path silently returns clean.
        origin = (row['started'] if row['client_id'] else row['created']) if row else None
        if row and row['status'] == 'processing' and origin and time.time() - origin > DEADLINE:
            db.execute("UPDATE jobs SET status='failed', stage='failed', error='processing_timeout' WHERE id=?", (job_id,))
            row = db.execute('SELECT * FROM jobs WHERE id=?', (job_id,)).fetchone()
    return dict(row) if row else None


def claim():
    with connect() as db:
        db.execute('BEGIN IMMEDIATE')
        row = db.execute("SELECT * FROM jobs WHERE status='processing' AND stage='queued' ORDER BY created LIMIT 1").fetchone()
        if row:
            db.execute("UPDATE jobs SET stage='decoding', started=?, attempts=attempts+1 WHERE id=?", (time.time(), row['id']))
            row = db.execute('SELECT * FROM jobs WHERE id=?', (row['id'],)).fetchone()
    return dict(row) if row else None


def stage(job_id, name):
    with connect() as db:
        db.execute("UPDATE jobs SET stage=? WHERE id=? AND status='processing'", (name, job_id))


def complete(job_id, result):
    with connect() as db:
        db.execute("UPDATE jobs SET status='done', stage='done', result=? WHERE id=? AND status='processing'",
                   (json.dumps(result, ensure_ascii=False, allow_nan=False), job_id))


def fail(job_id, error):
    with connect() as db:
        db.execute("UPDATE jobs SET status='failed', stage='failed', error=? WHERE id=? AND status='processing'", (error, job_id))


def recover():
    with connect() as db:
        db.execute("UPDATE jobs SET stage='queued',started=NULL WHERE status='processing' AND stage!='queued' AND attempts<2")
        db.execute("UPDATE jobs SET status='failed',stage='failed',error='worker_restarted' WHERE status='processing' AND stage!='queued'")
        rows = db.execute("SELECT id FROM jobs WHERE status IN ('done','failed')").fetchall()
    for row in rows:
        (UPLOADS / (row['id'] + '.mov')).unlink(missing_ok=True)


def queue_position(job_id):
    with connect() as db:
        return db.execute("SELECT COUNT(*) FROM jobs WHERE status='processing' AND created < (SELECT created FROM jobs WHERE id=?)", (job_id,)).fetchone()[0]


def cleanup():
    cutoff = time.time() - RETENTION_HOURS * 3600
    with connect() as db:
        # A queued job may expire through GET/admission before the worker claims
        # it. Remove its upload too, while retaining the status/result until TTL.
        rows = db.execute("SELECT id FROM jobs WHERE created < ? OR status IN ('done','failed')", (cutoff,)).fetchall()
        db.execute('DELETE FROM jobs WHERE created < ?', (cutoff,))
    for row in rows:
        (UPLOADS / (row['id'] + '.mov')).unlink(missing_ok=True)
    for path in (DATA / 'legal-audit').glob('*.json'):
        if path.stat().st_mtime < cutoff:
            path.unlink(missing_ok=True)
