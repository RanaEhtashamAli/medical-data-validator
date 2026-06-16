"""
Dataset registry and validation history (Phase 3d).

Tracks named datasets and links them to the immutable audit trail.
Researchers can register a dataset once, then query its full validation history.

Schema
------
datasets
    id           TEXT  PRIMARY KEY (UUID)
    name         TEXT  NOT NULL
    description  TEXT
    tenant       TEXT
    created_at   TEXT
    updated_at   TEXT
    tags         TEXT  (JSON array)
    metadata     TEXT  (JSON object)

dataset_runs
    id           TEXT  PRIMARY KEY (UUID)
    dataset_id   TEXT  REFERENCES datasets(id)
    audit_id     TEXT  (FK into audit_log.id)
    run_at       TEXT
    is_valid     INTEGER
    error_count  INTEGER
    warning_count INTEGER
"""

import json
import os
import sqlite3
import threading
import uuid
from datetime import datetime, timezone
from typing import Any, Dict, List, Optional

from .audit import AUDIT_DB_PATH, _lock as _audit_lock, _get_conn as _audit_get_conn

# Registry lives in the same SQLite file as the audit log for simplicity.
# Override with REGISTRY_DB_PATH if a separate store is preferred.
REGISTRY_DB_PATH = os.environ.get('REGISTRY_DB_PATH', AUDIT_DB_PATH)

_lock = threading.Lock()
_conn: Optional[sqlite3.Connection] = None


def _get_conn() -> sqlite3.Connection:
    global _conn
    if _conn is None:
        os.makedirs(os.path.dirname(REGISTRY_DB_PATH), exist_ok=True)
        _conn = sqlite3.connect(REGISTRY_DB_PATH, check_same_thread=False)
        _conn.row_factory = sqlite3.Row
        _init_schema(_conn)
    return _conn


def _init_schema(conn: sqlite3.Connection) -> None:
    conn.executescript("""
        CREATE TABLE IF NOT EXISTS datasets (
            id          TEXT PRIMARY KEY,
            name        TEXT NOT NULL,
            description TEXT,
            tenant      TEXT,
            created_at  TEXT NOT NULL,
            updated_at  TEXT NOT NULL,
            tags        TEXT,
            metadata    TEXT
        );

        CREATE UNIQUE INDEX IF NOT EXISTS idx_ds_name_tenant
            ON datasets(name, tenant);
        CREATE INDEX IF NOT EXISTS idx_ds_tenant ON datasets(tenant);

        CREATE TABLE IF NOT EXISTS dataset_runs (
            id            TEXT PRIMARY KEY,
            dataset_id    TEXT NOT NULL REFERENCES datasets(id),
            audit_id      TEXT,
            run_at        TEXT NOT NULL,
            is_valid      INTEGER,
            error_count   INTEGER,
            warning_count INTEGER
        );

        CREATE INDEX IF NOT EXISTS idx_runs_dataset ON dataset_runs(dataset_id);
        CREATE INDEX IF NOT EXISTS idx_runs_run_at  ON dataset_runs(run_at);
    """)
    conn.commit()


# ── Dataset CRUD ──────────────────────────────────────────────────────────────

def register_dataset(
    name: str,
    *,
    tenant: Optional[str] = None,
    description: Optional[str] = None,
    tags: Optional[List[str]] = None,
    metadata: Optional[Dict[str, Any]] = None,
) -> Dict[str, Any]:
    """Register a new dataset. Raises ValueError if name+tenant already exists."""
    now = datetime.now(timezone.utc).isoformat()
    ds_id = str(uuid.uuid4())
    with _lock:
        conn = _get_conn()
        try:
            conn.execute(
                """INSERT INTO datasets (id, name, description, tenant,
                   created_at, updated_at, tags, metadata)
                   VALUES (?,?,?,?,?,?,?,?)""",
                (
                    ds_id, name, description, tenant, now, now,
                    json.dumps(tags or []),
                    json.dumps(metadata or {}),
                ),
            )
            conn.commit()
        except sqlite3.IntegrityError:
            raise ValueError(f"Dataset '{name}' already exists for tenant '{tenant}'")
    return get_dataset(ds_id)


def get_dataset(dataset_id: str) -> Optional[Dict[str, Any]]:
    with _lock:
        conn = _get_conn()
        row = conn.execute(
            "SELECT * FROM datasets WHERE id = ?", (dataset_id,)
        ).fetchone()
    if not row:
        return None
    return _deserialize_dataset(dict(row))


def list_datasets(
    tenant: Optional[str] = None,
    tag: Optional[str] = None,
    limit: int = 100,
    offset: int = 0,
) -> List[Dict[str, Any]]:
    clauses, params = [], []
    if tenant:
        clauses.append("tenant = ?")
        params.append(tenant)
    where = f"WHERE {' AND '.join(clauses)}" if clauses else ""
    sql = f"SELECT * FROM datasets {where} ORDER BY created_at DESC LIMIT ? OFFSET ?"
    params += [limit, offset]
    with _lock:
        rows = _get_conn().execute(sql, params).fetchall()
    datasets = [_deserialize_dataset(dict(r)) for r in rows]
    if tag:
        datasets = [d for d in datasets if tag in d.get('tags', [])]
    return datasets


def update_dataset(
    dataset_id: str,
    *,
    description: Optional[str] = None,
    tags: Optional[List[str]] = None,
    metadata: Optional[Dict[str, Any]] = None,
) -> Optional[Dict[str, Any]]:
    """Partial update — only supplied fields are changed."""
    now = datetime.now(timezone.utc).isoformat()
    with _lock:
        conn = _get_conn()
        existing = conn.execute(
            "SELECT * FROM datasets WHERE id = ?", (dataset_id,)
        ).fetchone()
        if not existing:
            return None
        existing = dict(existing)

        new_desc = description if description is not None else existing['description']
        new_tags = json.dumps(tags) if tags is not None else existing['tags']
        new_meta = json.dumps(metadata) if metadata is not None else existing['metadata']

        conn.execute(
            """UPDATE datasets SET description=?, tags=?, metadata=?, updated_at=?
               WHERE id=?""",
            (new_desc, new_tags, new_meta, now, dataset_id),
        )
        conn.commit()
    return get_dataset(dataset_id)


def delete_dataset(dataset_id: str) -> bool:
    with _lock:
        conn = _get_conn()
        cur = conn.execute("DELETE FROM datasets WHERE id = ?", (dataset_id,))
        conn.execute("DELETE FROM dataset_runs WHERE dataset_id = ?", (dataset_id,))
        conn.commit()
    return cur.rowcount > 0


# ── Run history ───────────────────────────────────────────────────────────────

def record_run(
    dataset_id: str,
    *,
    audit_id: Optional[str] = None,
    is_valid: Optional[bool] = None,
    error_count: int = 0,
    warning_count: int = 0,
) -> str:
    """Append a validation run to a dataset's history. Returns the run UUID."""
    run_id = str(uuid.uuid4())
    now = datetime.now(timezone.utc).isoformat()
    with _lock:
        conn = _get_conn()
        conn.execute(
            """INSERT INTO dataset_runs
               (id, dataset_id, audit_id, run_at, is_valid, error_count, warning_count)
               VALUES (?,?,?,?,?,?,?)""",
            (
                run_id, dataset_id, audit_id, now,
                int(is_valid) if is_valid is not None else None,
                error_count, warning_count,
            ),
        )
        conn.commit()
    return run_id


def get_run_history(
    dataset_id: str,
    limit: int = 50,
    offset: int = 0,
) -> List[Dict[str, Any]]:
    with _lock:
        rows = _get_conn().execute(
            """SELECT * FROM dataset_runs WHERE dataset_id = ?
               ORDER BY run_at DESC LIMIT ? OFFSET ?""",
            (dataset_id, limit, offset),
        ).fetchall()
    return [dict(r) for r in rows]


def count_runs(dataset_id: str) -> int:
    with _lock:
        return _get_conn().execute(
            "SELECT COUNT(*) FROM dataset_runs WHERE dataset_id = ?", (dataset_id,)
        ).fetchone()[0]


# ── Helpers ───────────────────────────────────────────────────────────────────

def _deserialize_dataset(d: Dict[str, Any]) -> Dict[str, Any]:
    for field in ('tags', 'metadata'):
        if d.get(field):
            try:
                d[field] = json.loads(d[field])
            except Exception:
                pass
    return d


# ── Flask route registration ──────────────────────────────────────────────────

def register_registry_routes(app) -> None:
    """Attach /api/registry/* routes to a Flask app."""
    from flask import request, jsonify, g

    try:
        from medical_data_validator.auth import login_required, role_required
    except ImportError:
        from ..auth import login_required, role_required

    @app.route('/api/registry/datasets', methods=['GET'])
    @login_required
    def list_datasets_endpoint():
        tenant = g.tenant if g.role != 'admin' else request.args.get('tenant', g.tenant)
        datasets = list_datasets(
            tenant=tenant,
            tag=request.args.get('tag'),
            limit=min(int(request.args.get('limit', 100)), 1000),
            offset=int(request.args.get('offset', 0)),
        )
        return jsonify({'total': len(datasets), 'datasets': datasets})

    @app.route('/api/registry/datasets', methods=['POST'])
    @role_required('data-steward', 'admin')
    def create_dataset_endpoint():
        data = request.get_json(silent=True) or {}
        name = data.get('name', '').strip()
        if not name:
            return jsonify({'error': 'name is required'}), 400
        tenant = data.get('tenant', g.tenant)
        try:
            ds = register_dataset(
                name,
                tenant=tenant,
                description=data.get('description'),
                tags=data.get('tags'),
                metadata=data.get('metadata'),
            )
            return jsonify(ds), 201
        except ValueError as exc:
            return jsonify({'error': str(exc)}), 409

    @app.route('/api/registry/datasets/<dataset_id>', methods=['GET'])
    @login_required
    def get_dataset_endpoint(dataset_id):
        ds = get_dataset(dataset_id)
        if not ds:
            return jsonify({'error': 'Dataset not found'}), 404
        if g.role != 'admin' and ds.get('tenant') != g.tenant:
            return jsonify({'error': 'Forbidden'}), 403
        return jsonify(ds)

    @app.route('/api/registry/datasets/<dataset_id>', methods=['PATCH'])
    @role_required('data-steward', 'admin')
    def update_dataset_endpoint(dataset_id):
        ds = get_dataset(dataset_id)
        if not ds:
            return jsonify({'error': 'Dataset not found'}), 404
        if g.role != 'admin' and ds.get('tenant') != g.tenant:
            return jsonify({'error': 'Forbidden'}), 403
        data = request.get_json(silent=True) or {}
        updated = update_dataset(
            dataset_id,
            description=data.get('description'),
            tags=data.get('tags'),
            metadata=data.get('metadata'),
        )
        return jsonify(updated)

    @app.route('/api/registry/datasets/<dataset_id>', methods=['DELETE'])
    @role_required('admin')
    def delete_dataset_endpoint(dataset_id):
        ok = delete_dataset(dataset_id)
        if not ok:
            return jsonify({'error': 'Dataset not found'}), 404
        return jsonify({'deleted': dataset_id})

    @app.route('/api/registry/datasets/<dataset_id>/history', methods=['GET'])
    @login_required
    def get_history_endpoint(dataset_id):
        ds = get_dataset(dataset_id)
        if not ds:
            return jsonify({'error': 'Dataset not found'}), 404
        if g.role != 'admin' and ds.get('tenant') != g.tenant:
            return jsonify({'error': 'Forbidden'}), 403
        runs = get_run_history(
            dataset_id,
            limit=min(int(request.args.get('limit', 50)), 500),
            offset=int(request.args.get('offset', 0)),
        )
        return jsonify({'total': count_runs(dataset_id), 'runs': runs})

    @app.route('/api/registry/datasets/<dataset_id>/runs', methods=['POST'])
    @role_required('data-steward', 'admin')
    def record_run_endpoint(dataset_id):
        ds = get_dataset(dataset_id)
        if not ds:
            return jsonify({'error': 'Dataset not found'}), 404
        if g.role != 'admin' and ds.get('tenant') != g.tenant:
            return jsonify({'error': 'Forbidden'}), 403
        data = request.get_json(silent=True) or {}
        run_id = record_run(
            dataset_id,
            audit_id=data.get('audit_id'),
            is_valid=data.get('is_valid'),
            error_count=int(data.get('error_count', 0)),
            warning_count=int(data.get('warning_count', 0)),
        )
        return jsonify({'run_id': run_id}), 201
