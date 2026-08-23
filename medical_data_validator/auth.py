"""
Authentication and multi-tenancy for the Medical Data Validator API.

Provides JWT-based auth with three roles:
  admin        — full access, user management
  data-steward — validate, anonymize, view audit log
  read-only    — view results and audit log only

Each tenant is identified by an API key header (X-API-Key).
Users belong to one tenant; their access is scoped to that tenant's data.
"""

import os
import hashlib
import hmac
import secrets
import sqlite3
import threading
import time
from collections.abc import MutableMapping
from datetime import datetime, timezone, timedelta
from functools import wraps
from typing import Dict, List, Optional, Any

import jwt
from flask import request, jsonify, g

# ── Configuration ────────────────────────────────────────────────────────────

JWT_SECRET = os.environ.get('JWT_SECRET', secrets.token_hex(32))
JWT_ALGORITHM = 'HS256'
JWT_EXPIRY_SECONDS = int(os.environ.get('JWT_EXPIRY_SECONDS', 3600))

ROLES = ('admin', 'data-steward', 'read-only')
ROLE_HIERARCHY = {'admin': 3, 'data-steward': 2, 'read-only': 1}


# ── User/tenant store (SQLite-backed, shared across worker processes) ───────
#
# A plain in-memory dict here was invisible across Gunicorn's separate
# worker processes: a user or tenant created on worker A didn't exist as
# far as worker B was concerned, so an immediately-following request (e.g.
# deactivate right after create) failed or succeeded depending on which
# worker handled it. _USERS/_TENANTS below keep the exact same dict
# interface every call site (and every existing test) already uses --
# `x in _USERS`, `_USERS[k]`, `_USERS[k] = {...}`, `.pop()`, `.items()`,
# `.clear()`/`.update()` for snapshot/restore -- but the data itself lives
# in SQLite, matching the pattern already used by audit.py/jobs.py/registry.py.

def _hash_password(password: str) -> str:
    salt = secrets.token_hex(16)
    h = hashlib.pbkdf2_hmac('sha256', password.encode(), salt.encode(), 260_000)
    return f"{salt}:{h.hex()}"


def _verify_password(password: str, stored: str) -> bool:
    try:
        salt, h = stored.split(':', 1)
        expected = hashlib.pbkdf2_hmac('sha256', password.encode(), salt.encode(), 260_000)
        return hmac.compare_digest(expected.hex(), h)
    except Exception:
        return False


_DEFAULT_DB = os.path.join(
    os.environ.get('AUTH_DB_DIR', os.path.expanduser('~/.medical_validator')),
    'auth.db'
)
AUTH_DB_PATH = os.environ.get('AUTH_DB_PATH', _DEFAULT_DB)

_lock = threading.Lock()
_conn: Optional[sqlite3.Connection] = None


def _get_conn() -> sqlite3.Connection:
    global _conn
    if _conn is None:
        from ._sqlite_store import connect
        _conn = connect(AUTH_DB_PATH, 'auth.db')
        _conn.row_factory = sqlite3.Row
        _init_schema(_conn)
        _seed_defaults_if_empty(_conn)
    return _conn


def _init_schema(conn: sqlite3.Connection) -> None:
    conn.executescript("""
        CREATE TABLE IF NOT EXISTS users (
            username      TEXT PRIMARY KEY,
            password_hash TEXT NOT NULL,
            role          TEXT NOT NULL,
            tenant        TEXT NOT NULL,
            active        INTEGER NOT NULL DEFAULT 1
        );
        CREATE TABLE IF NOT EXISTS tenants (
            tenant_id TEXT PRIMARY KEY,
            name      TEXT NOT NULL,
            api_key   TEXT NOT NULL
        );
    """)
    conn.commit()


def _seed_defaults_if_empty(conn: sqlite3.Connection) -> None:
    """First-boot bootstrap only -- never overwrites an existing admin
    account or default tenant on a later restart, so a since-changed
    ADMIN_PASSWORD env var or a manually-edited tenant record isn't
    silently reset every time the process restarts."""
    if conn.execute("SELECT COUNT(*) FROM users").fetchone()[0] == 0:
        conn.execute(
            "INSERT INTO users (username, password_hash, role, tenant, active) VALUES (?, ?, ?, ?, 1)",
            ('admin', _hash_password(os.environ.get('ADMIN_PASSWORD', 'change-me')), 'admin', 'default'),
        )
    if conn.execute("SELECT COUNT(*) FROM tenants").fetchone()[0] == 0:
        conn.execute(
            "INSERT INTO tenants (tenant_id, name, api_key) VALUES (?, ?, ?)",
            ('default', 'Default Tenant', os.environ.get('DEFAULT_TENANT_API_KEY', '')),
        )
    conn.commit()


class _UsersStore(MutableMapping):
    def __getitem__(self, username):
        row = _get_conn().execute(
            "SELECT password_hash, role, tenant, active FROM users WHERE username = ?", (username,)
        ).fetchone()
        if row is None:
            raise KeyError(username)
        return {'password_hash': row['password_hash'], 'role': row['role'],
                'tenant': row['tenant'], 'active': bool(row['active'])}

    def __setitem__(self, username, value):
        with _lock:
            conn = _get_conn()
            conn.execute(
                "INSERT INTO users (username, password_hash, role, tenant, active) VALUES (?, ?, ?, ?, ?) "
                "ON CONFLICT(username) DO UPDATE SET password_hash=excluded.password_hash, "
                "role=excluded.role, tenant=excluded.tenant, active=excluded.active",
                (username, value['password_hash'], value['role'], value['tenant'],
                 int(bool(value.get('active', True)))),
            )
            conn.commit()

    def __delitem__(self, username):
        with _lock:
            conn = _get_conn()
            cur = conn.execute("DELETE FROM users WHERE username = ?", (username,))
            conn.commit()
            if cur.rowcount == 0:
                raise KeyError(username)

    def __iter__(self):
        return iter(r['username'] for r in _get_conn().execute("SELECT username FROM users"))

    def __len__(self):
        return _get_conn().execute("SELECT COUNT(*) FROM users").fetchone()[0]


class _TenantsStore(MutableMapping):
    def __getitem__(self, tenant_id):
        row = _get_conn().execute(
            "SELECT name, api_key FROM tenants WHERE tenant_id = ?", (tenant_id,)
        ).fetchone()
        if row is None:
            raise KeyError(tenant_id)
        return {'name': row['name'], 'api_key': row['api_key']}

    def __setitem__(self, tenant_id, value):
        with _lock:
            conn = _get_conn()
            conn.execute(
                "INSERT INTO tenants (tenant_id, name, api_key) VALUES (?, ?, ?) "
                "ON CONFLICT(tenant_id) DO UPDATE SET name=excluded.name, api_key=excluded.api_key",
                (tenant_id, value['name'], value['api_key']),
            )
            conn.commit()

    def __delitem__(self, tenant_id):
        with _lock:
            conn = _get_conn()
            cur = conn.execute("DELETE FROM tenants WHERE tenant_id = ?", (tenant_id,))
            conn.commit()
            if cur.rowcount == 0:
                raise KeyError(tenant_id)

    def __iter__(self):
        return iter(r['tenant_id'] for r in _get_conn().execute("SELECT tenant_id FROM tenants"))

    def __len__(self):
        return _get_conn().execute("SELECT COUNT(*) FROM tenants").fetchone()[0]


_USERS: MutableMapping = _UsersStore()
_TENANTS: MutableMapping = _TenantsStore()


# ── Token helpers ─────────────────────────────────────────────────────────────

def create_token(username: str, role: str, tenant: str) -> str:
    payload = {
        'sub': username,
        'role': role,
        'tenant': tenant,
        'iat': int(time.time()),
        'exp': int(time.time()) + JWT_EXPIRY_SECONDS,
    }
    return jwt.encode(payload, JWT_SECRET, algorithm=JWT_ALGORITHM)


def decode_token(token: str) -> Dict[str, Any]:
    return jwt.decode(token, JWT_SECRET, algorithms=[JWT_ALGORITHM])


# ── Auth decorators ───────────────────────────────────────────────────────────

def _extract_token() -> Optional[str]:
    auth = request.headers.get('Authorization', '')
    if auth.startswith('Bearer '):
        return auth[7:]
    return None


def _extract_tenant() -> Optional[str]:
    """Identify tenant from X-API-Key header (optional; falls back to JWT claim)."""
    api_key = request.headers.get('X-API-Key', '')
    if api_key:
        for tenant_id, tenant in _TENANTS.items():
            if tenant.get('api_key') and hmac.compare_digest(tenant['api_key'], api_key):
                return tenant_id
    return None


def login_required(f):
    """Decorator: require a valid JWT. Sets g.user, g.role, g.tenant."""
    @wraps(f)
    def decorated(*args, **kwargs):
        token = _extract_token()
        if not token:
            return jsonify({'error': 'Authentication required'}), 401
        try:
            payload = decode_token(token)
        except jwt.ExpiredSignatureError:
            return jsonify({'error': 'Token expired'}), 401
        except jwt.InvalidTokenError:
            return jsonify({'error': 'Invalid token'}), 401

        username = payload.get('sub')
        user = _USERS.get(username)
        if not user or not user.get('active'):
            return jsonify({'error': 'User not found or inactive'}), 401

        g.user = username
        g.role = payload.get('role', 'read-only')
        g.tenant = payload.get('tenant', 'default')

        # Allow API-key tenant override (narrows, never elevates)
        api_tenant = _extract_tenant()
        if api_tenant and api_tenant != g.tenant and g.role != 'admin':
            return jsonify({'error': 'API key tenant mismatch'}), 403

        return f(*args, **kwargs)
    return decorated


def role_required(*required_roles: str):
    """Decorator: require the caller's role level to be at least that of the
    lowest-ranked named role (e.g. role_required('data-steward', 'admin')
    admits both data-steward and admin, since data-steward is the
    lowest-ranked of the two -- it does NOT mean literal membership in the
    named set).

    Raises ValueError immediately (at decoration time, i.e. when the module
    defining the route is imported) if any named role isn't a real key in
    ROLE_HIERARCHY, so a typo fails loudly at startup instead of silently
    resolving to level 0 and admitting every authenticated caller.
    """
    unknown = [r for r in required_roles if r not in ROLE_HIERARCHY]
    if unknown:
        raise ValueError(
            f"role_required() got unknown role(s): {unknown}. "
            f"Valid roles: {list(ROLE_HIERARCHY)}"
        )

    def decorator(f):
        @wraps(f)
        @login_required
        def decorated(*args, **kwargs):
            caller_level = ROLE_HIERARCHY.get(g.role, 0)
            required_level = min(ROLE_HIERARCHY.get(r, 0) for r in required_roles)
            if caller_level < required_level:
                return jsonify({'error': f'Role {required_roles} required'}), 403
            return f(*args, **kwargs)
        return decorated
    return decorator


# ── Module-level account functions (Phase B extraction) ──────────────────────

def list_user_accounts() -> List[Dict[str, Any]]:
    return [
        {'username': u, 'role': d['role'], 'tenant': d['tenant'], 'active': d['active']}
        for u, d in _USERS.items()
    ]


def create_user_account(username: str, password: str, role: str = 'read-only', tenant: str = 'default') -> Dict[str, Any]:
    username = (username or '').strip()
    if not username or not password:
        raise ValueError('username and password required')
    if username in _USERS:
        raise ValueError('User already exists')
    if role not in ROLES:
        raise ValueError(f'role must be one of {ROLES}')
    _USERS[username] = {
        'password_hash': _hash_password(password),
        'role': role,
        'tenant': tenant,
        'active': True,
    }
    return {'created': username, 'role': role, 'tenant': tenant}


def deactivate_user_account(username: str) -> None:
    if username not in _USERS:
        raise ValueError('User not found')
    # Fetch-modify-writeback rather than `_USERS[username]['active'] = False`:
    # __getitem__ builds a fresh dict from the DB on every call, so mutating
    # it in place would touch only that throwaway dict, never persisting.
    user = _USERS[username]
    user['active'] = False
    _USERS[username] = user


def create_tenant_account(tenant_id: str, name: Optional[str] = None) -> Dict[str, Any]:
    tenant_id = (tenant_id or '').strip()
    if not tenant_id:
        raise ValueError('tenant_id required')
    if tenant_id in _TENANTS:
        raise ValueError('Tenant already exists')
    api_key = secrets.token_hex(32)
    _TENANTS[tenant_id] = {'name': name or tenant_id, 'api_key': api_key}
    return {'tenant_id': tenant_id, 'api_key': api_key}


# ── Auth routes (register with Flask app via register_auth_routes) ────────────

def register_auth_routes(app):
    """Attach /api/auth/* routes to a Flask app."""

    @app.route('/api/auth/token', methods=['POST'])
    def get_token():
        """Exchange username + password for a JWT."""
        data = request.get_json(silent=True) or {}
        username = data.get('username', '').strip()
        password = data.get('password', '')

        user = _USERS.get(username)
        if not user or not user.get('active') or not _verify_password(password, user['password_hash']):
            return jsonify({'error': 'Invalid credentials'}), 401

        token = create_token(username, user['role'], user['tenant'])
        return jsonify({
            'access_token': token,
            'token_type': 'bearer',
            'expires_in': JWT_EXPIRY_SECONDS,
            'role': user['role'],
            'tenant': user['tenant'],
        })

    @app.route('/api/auth/me', methods=['GET'])
    @login_required
    def me():
        """Return info about the currently authenticated user."""
        return jsonify({'username': g.user, 'role': g.role, 'tenant': g.tenant})

    @app.route('/api/auth/users', methods=['GET'])
    @role_required('admin')
    def list_users():
        return jsonify(list_user_accounts())

    @app.route('/api/auth/users', methods=['POST'])
    @role_required('admin')
    def create_user():
        data = request.get_json(silent=True) or {}
        try:
            result = create_user_account(
                data.get('username', ''), data.get('password', ''),
                role=data.get('role', 'read-only'), tenant=data.get('tenant', g.tenant),
            )
            return jsonify(result), 201
        except ValueError as exc:
            code = 409 if 'already exists' in str(exc) else 400
            return jsonify({'error': str(exc)}), code

    @app.route('/api/auth/users/<username>', methods=['DELETE'])
    @role_required('admin')
    def deactivate_user(username):
        if username == g.user:
            return jsonify({'error': 'Cannot deactivate yourself'}), 400
        try:
            deactivate_user_account(username)
            return jsonify({'deactivated': username})
        except ValueError as exc:
            return jsonify({'error': str(exc)}), 404

    @app.route('/api/auth/tenants', methods=['POST'])
    @role_required('admin')
    def create_tenant():
        data = request.get_json(silent=True) or {}
        try:
            result = create_tenant_account(data.get('tenant_id', ''), data.get('name'))
            return jsonify(result), 201
        except ValueError as exc:
            code = 409 if 'already exists' in str(exc) else 400
            return jsonify({'error': str(exc)}), code
