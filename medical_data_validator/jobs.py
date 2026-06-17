"""
Async validation job queue (Phase 3g).

Provides a lightweight, always-available job queue backed by SQLite with a
background worker thread.  When Celery + Redis are available (install the
[celery] extra), jobs are dispatched to Celery instead for horizontal scale.

Job lifecycle:  pending → running → completed | failed

REST surface (registered via register_job_routes):
  POST /api/jobs          — submit a new job
  GET  /api/jobs/<id>     — poll status / fetch result
  GET  /api/jobs          — list recent jobs (scoped to tenant)
"""

import json
import os
import queue
import sqlite3
import tempfile
import threading
import traceback
import uuid
from datetime import datetime, timezone
from typing import Any, Dict, List, Optional

import pandas as pd

# ── Storage ───────────────────────────────────────────────────────────────────

_DEFAULT_DB = os.path.join(
    os.environ.get('JOBS_DB_DIR', os.path.expanduser('~/.medical_validator')),
    'jobs.db',
)
JOBS_DB_PATH = os.environ.get('JOBS_DB_PATH', _DEFAULT_DB)

_lock = threading.Lock()
_conn: Optional[sqlite3.Connection] = None


def _get_conn() -> sqlite3.Connection:
    global _conn
    if _conn is None:
        os.makedirs(os.path.dirname(JOBS_DB_PATH), exist_ok=True)
        _conn = sqlite3.connect(JOBS_DB_PATH, check_same_thread=False)
        _conn.row_factory = sqlite3.Row
        _init_schema(_conn)
    return _conn


def _init_schema(conn: sqlite3.Connection) -> None:
    conn.executescript("""
        CREATE TABLE IF NOT EXISTS jobs (
            id          TEXT PRIMARY KEY,
            tenant      TEXT,
            username    TEXT,
            job_type    TEXT NOT NULL,
            status      TEXT NOT NULL DEFAULT 'pending',
            payload     TEXT,
            result      TEXT,
            error       TEXT,
            created_at  TEXT NOT NULL,
            started_at  TEXT,
            finished_at TEXT
        );
        CREATE INDEX IF NOT EXISTS idx_jobs_tenant  ON jobs(tenant);
        CREATE INDEX IF NOT EXISTS idx_jobs_status  ON jobs(status);
        CREATE INDEX IF NOT EXISTS idx_jobs_created ON jobs(created_at);
    """)
    conn.commit()


# ── Job CRUD ──────────────────────────────────────────────────────────────────

def create_job(
    job_type: str,
    payload: Dict[str, Any],
    *,
    tenant: Optional[str] = None,
    username: Optional[str] = None,
) -> str:
    """Persist a new job record (status=pending). Returns the job UUID."""
    job_id = str(uuid.uuid4())
    now = datetime.now(timezone.utc).isoformat()
    with _lock:
        _get_conn().execute(
            """INSERT INTO jobs (id, tenant, username, job_type, status,
               payload, created_at) VALUES (?,?,?,?,?,?,?)""",
            (job_id, tenant, username, job_type, 'pending',
             json.dumps(payload), now),
        )
        _get_conn().commit()
    return job_id


def get_job(job_id: str) -> Optional[Dict[str, Any]]:
    with _lock:
        row = _get_conn().execute(
            "SELECT * FROM jobs WHERE id = ?", (job_id,)
        ).fetchone()
    if not row:
        return None
    return _deserialize_job(dict(row))


def list_jobs(
    tenant: Optional[str] = None,
    status: Optional[str] = None,
    limit: int = 50,
    offset: int = 0,
) -> List[Dict[str, Any]]:
    clauses, params = [], []
    if tenant:
        clauses.append("tenant = ?"); params.append(tenant)
    if status:
        clauses.append("status = ?"); params.append(status)
    where = f"WHERE {' AND '.join(clauses)}" if clauses else ""
    sql = f"SELECT * FROM jobs {where} ORDER BY created_at DESC LIMIT ? OFFSET ?"
    params += [limit, offset]
    with _lock:
        rows = _get_conn().execute(sql, params).fetchall()
    return [_deserialize_job(dict(r)) for r in rows]


def _update_job(job_id: str, **fields) -> None:
    set_clause = ", ".join(f"{k} = ?" for k in fields)
    with _lock:
        _get_conn().execute(
            f"UPDATE jobs SET {set_clause} WHERE id = ?",
            list(fields.values()) + [job_id],
        )
        _get_conn().commit()


def _deserialize_job(d: Dict[str, Any]) -> Dict[str, Any]:
    for field in ('payload', 'result'):
        if d.get(field):
            try:
                d[field] = json.loads(d[field])
            except Exception:
                pass
    return d


# ── In-process worker ─────────────────────────────────────────────────────────

_job_queue: queue.Queue = queue.Queue()
_worker_started = False
_worker_lock = threading.Lock()


def _run_job(job_id: str, job_type: str, payload: Dict[str, Any]) -> None:
    """Execute one job synchronously (called from the worker thread)."""
    now = datetime.now(timezone.utc).isoformat
    _update_job(job_id, status='running', started_at=datetime.now(timezone.utc).isoformat())

    try:
        if job_type == 'validate':
            result = _execute_validate(payload)
        elif job_type == 'anonymize':
            result = _execute_anonymize(payload)
        else:
            raise ValueError(f"Unknown job_type: {job_type!r}")

        _update_job(
            job_id,
            status='completed',
            result=json.dumps(result),
            finished_at=datetime.now(timezone.utc).isoformat(),
        )
    except Exception as exc:
        _update_job(
            job_id,
            status='failed',
            error=f"{type(exc).__name__}: {exc}\n{traceback.format_exc()}",
            finished_at=datetime.now(timezone.utc).isoformat(),
        )


def _execute_validate(payload: Dict[str, Any]) -> Dict[str, Any]:
    from .core import MedicalDataValidator
    data = payload.get('data', {})
    df = pd.DataFrame(data)
    validator = MedicalDataValidator(
        enable_compliance=payload.get('enable_compliance', True),
        enable_analytics=payload.get('enable_analytics', False),
        enable_monitoring=False,
    )
    result = validator.validate(df)
    return result.to_dict()


def _execute_anonymize(payload: Dict[str, Any]) -> Dict[str, Any]:
    from .core import MedicalDataValidator
    data = payload.get('data', {})
    df = pd.DataFrame(data)
    validator = MedicalDataValidator(
        enable_compliance=False, enable_analytics=False, enable_monitoring=False
    )
    columns = payload.get('columns')
    method = payload.get('method', 'hipaa_safe_harbor')
    result_df = validator.anonymize(df, columns=columns, method=method)
    return {'data': result_df.to_dict(orient='records'), 'rows': len(result_df)}


def _worker_loop() -> None:
    while True:
        job_id, job_type, payload = _job_queue.get()
        try:
            _run_job(job_id, job_type, payload)
        except Exception:
            pass
        finally:
            _job_queue.task_done()


def _ensure_worker() -> None:
    global _worker_started
    with _worker_lock:
        if not _worker_started:
            t = threading.Thread(target=_worker_loop, daemon=True, name='mdv-job-worker')
            t.start()
            _worker_started = True


def submit_job(
    job_type: str,
    payload: Dict[str, Any],
    *,
    tenant: Optional[str] = None,
    username: Optional[str] = None,
) -> str:
    """
    Create a job record and enqueue it for the background worker.

    Returns the job UUID immediately (non-blocking).
    """
    _ensure_worker()
    job_id = create_job(job_type, payload, tenant=tenant, username=username)
    _job_queue.put((job_id, job_type, payload))
    return job_id


# ── Optional Celery dispatch ──────────────────────────────────────────────────

def _celery_available() -> bool:
    try:
        import celery  # noqa: F401
        broker = os.environ.get('CELERY_BROKER_URL', '')
        return bool(broker)
    except ImportError:
        return False


# ── Flask route registration ──────────────────────────────────────────────────

def register_job_routes(app) -> None:
    """Attach /api/jobs routes to a Flask app."""
    from flask import request, jsonify, g

    try:
        from medical_data_validator.auth import login_required, role_required
    except ImportError:
        from ..auth import login_required, role_required

    @app.route('/api/jobs', methods=['POST'])
    @role_required('data-steward', 'admin')
    def submit_job_endpoint():
        data = request.get_json(silent=True) or {}
        job_type = data.get('job_type', '').strip()
        if job_type not in ('validate', 'anonymize'):
            return jsonify({'error': "job_type must be 'validate' or 'anonymize'"}), 400
        payload = data.get('payload', {})
        if not isinstance(payload, dict):
            return jsonify({'error': 'payload must be a JSON object'}), 400

        job_id = submit_job(job_type, payload, tenant=g.tenant, username=g.user)
        job = get_job(job_id)
        return jsonify(job), 202

    @app.route('/api/jobs', methods=['GET'])
    @login_required
    def list_jobs_endpoint():
        tenant = g.tenant if g.role != 'admin' else request.args.get('tenant', g.tenant)
        jobs = list_jobs(
            tenant=tenant,
            status=request.args.get('status'),
            limit=min(int(request.args.get('limit', 50)), 200),
            offset=int(request.args.get('offset', 0)),
        )
        return jsonify({'total': len(jobs), 'jobs': jobs})

    @app.route('/api/jobs/<job_id>', methods=['GET'])
    @login_required
    def get_job_endpoint(job_id):
        job = get_job(job_id)
        if not job:
            return jsonify({'error': 'Job not found'}), 404
        if g.role != 'admin' and job.get('tenant') != g.tenant:
            return jsonify({'error': 'Forbidden'}), 403
        return jsonify(job)
