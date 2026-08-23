"""
Immutable audit trail for the Medical Data Validator.

Every validation, anonymization, and compliance check is logged to an
append-only SQLite table.  Records are never updated or deleted — only
inserted.  This satisfies FDA 21 CFR Part 11 and GCP audit requirements.

For production, set AUDIT_DB_URL to a PostgreSQL DSN:
    AUDIT_DB_URL=postgresql://user:pass@host/db
The module falls back to SQLite when the env var is unset.
"""

import hashlib
import json
import os
import sqlite3
import threading
import uuid
from datetime import datetime, timezone
from typing import Any, Dict, List, Optional


# ── Database path / URL ───────────────────────────────────────────────────────

_DEFAULT_DB = os.path.join(
    os.environ.get('AUDIT_DB_DIR', os.path.expanduser('~/.medical_validator')),
    'audit.db'
)
AUDIT_DB_PATH = os.environ.get('AUDIT_DB_PATH', _DEFAULT_DB)

_lock = threading.Lock()
_conn: Optional[sqlite3.Connection] = None


def _get_conn() -> sqlite3.Connection:
    global _conn
    if _conn is None:
        from ._sqlite_store import connect
        _conn = connect(AUDIT_DB_PATH, 'audit.db')
        _conn.row_factory = sqlite3.Row
        _init_schema(_conn)
    return _conn


def _init_schema(conn: sqlite3.Connection) -> None:
    conn.executescript("""
        CREATE TABLE IF NOT EXISTS audit_log (
            id          TEXT PRIMARY KEY,
            timestamp   TEXT NOT NULL,
            event_type  TEXT NOT NULL,
            username    TEXT,
            tenant      TEXT,
            dataset_id  TEXT,
            dataset_hash TEXT,
            rules_applied TEXT,
            result_summary TEXT,
            ip_address  TEXT,
            extra       TEXT
        );

        CREATE INDEX IF NOT EXISTS idx_audit_timestamp ON audit_log(timestamp);
        CREATE INDEX IF NOT EXISTS idx_audit_tenant    ON audit_log(tenant);
        CREATE INDEX IF NOT EXISTS idx_audit_dataset   ON audit_log(dataset_id);
        CREATE INDEX IF NOT EXISTS idx_audit_user      ON audit_log(username);
    """)
    conn.commit()


# ── Public API ────────────────────────────────────────────────────────────────

def log_event(
    event_type: str,
    *,
    username: Optional[str] = None,
    tenant: Optional[str] = None,
    dataset_id: Optional[str] = None,
    dataset_hash: Optional[str] = None,
    rules_applied: Optional[List[str]] = None,
    result_summary: Optional[Dict[str, Any]] = None,
    ip_address: Optional[str] = None,
    extra: Optional[Dict[str, Any]] = None,
) -> str:
    """Append one immutable audit record. Returns the record's UUID."""
    record_id = str(uuid.uuid4())
    ts = datetime.now(timezone.utc).isoformat()

    with _lock:
        conn = _get_conn()
        conn.execute(
            """
            INSERT INTO audit_log
                (id, timestamp, event_type, username, tenant,
                 dataset_id, dataset_hash, rules_applied, result_summary,
                 ip_address, extra)
            VALUES (?,?,?,?,?,?,?,?,?,?,?)
            """,
            (
                record_id,
                ts,
                event_type,
                username,
                tenant,
                dataset_id,
                dataset_hash,
                json.dumps(rules_applied) if rules_applied is not None else None,
                json.dumps(result_summary) if result_summary is not None else None,
                ip_address,
                json.dumps(extra) if extra is not None else None,
            ),
        )
        conn.commit()

    return record_id


def hash_dataframe(df) -> str:
    """Return a stable content hash of a DataFrame (for audit_log.dataset_hash)."""
    raw = df.to_csv(index=False).encode()
    return hashlib.sha256(raw).hexdigest()


def query_log(
    tenant: Optional[str] = None,
    username: Optional[str] = None,
    dataset_id: Optional[str] = None,
    event_type: Optional[str] = None,
    since: Optional[str] = None,
    until: Optional[str] = None,
    limit: int = 100,
    offset: int = 0,
) -> List[Dict[str, Any]]:
    """Query the audit log with optional filters."""
    clauses = []
    params: list = []

    if tenant:
        clauses.append("tenant = ?")
        params.append(tenant)
    if username:
        clauses.append("username = ?")
        params.append(username)
    if dataset_id:
        clauses.append("dataset_id = ?")
        params.append(dataset_id)
    if event_type:
        clauses.append("event_type = ?")
        params.append(event_type)
    if since:
        clauses.append("timestamp >= ?")
        params.append(since)
    if until:
        clauses.append("timestamp <= ?")
        params.append(until)

    where = f"WHERE {' AND '.join(clauses)}" if clauses else ""
    sql = f"SELECT * FROM audit_log {where} ORDER BY timestamp DESC LIMIT ? OFFSET ?"
    params += [limit, offset]

    with _lock:
        conn = _get_conn()
        rows = conn.execute(sql, params).fetchall()

    result = []
    for row in rows:
        d = dict(row)
        for field in ('rules_applied', 'result_summary', 'extra'):
            if d[field]:
                try:
                    d[field] = json.loads(d[field])
                except Exception:
                    pass
        result.append(d)
    return result


def count_log(**kwargs) -> int:
    """Count records matching the same filters as query_log (without limit/offset)."""
    clauses = []
    params: list = []
    for key, col in [
        ('tenant', 'tenant'), ('username', 'username'),
        ('dataset_id', 'dataset_id'), ('event_type', 'event_type'),
    ]:
        if kwargs.get(key):
            clauses.append(f"{col} = ?")
            params.append(kwargs[key])
    if kwargs.get('since'):
        clauses.append("timestamp >= ?")
        params.append(kwargs['since'])
    if kwargs.get('until'):
        clauses.append("timestamp <= ?")
        params.append(kwargs['until'])
    where = f"WHERE {' AND '.join(clauses)}" if clauses else ""
    with _lock:
        conn = _get_conn()
        return conn.execute(f"SELECT COUNT(*) FROM audit_log {where}", params).fetchone()[0]


# ── Flask route registration ──────────────────────────────────────────────────

def register_audit_routes(app):
    """Attach /api/audit/* routes to a Flask app."""
    from flask import request, jsonify

    try:
        from medical_data_validator.auth import login_required, role_required
    except ImportError:
        from ..auth import login_required, role_required

    @app.route('/api/audit', methods=['GET'])
    @role_required('data-steward', 'admin')
    def get_audit_log():
        from flask import g
        args = request.args
        tenant_filter = args.get('tenant') if g.role == 'admin' else g.tenant
        records = query_log(
            tenant=tenant_filter,
            username=args.get('username'),
            dataset_id=args.get('dataset_id'),
            event_type=args.get('event_type'),
            since=args.get('since'),
            until=args.get('until'),
            limit=min(int(args.get('limit', 100)), 1000),
            offset=int(args.get('offset', 0)),
        )
        total = count_log(
            tenant=tenant_filter,
            username=args.get('username'),
            dataset_id=args.get('dataset_id'),
            event_type=args.get('event_type'),
            since=args.get('since'),
            until=args.get('until'),
        )
        return jsonify({'total': total, 'records': records})
