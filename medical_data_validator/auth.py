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
import time
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


# ── In-memory user store (replace with DB in production) ─────────────────────

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


# Default admin seeded from env; nothing is hardcoded in source.
_ADMIN_PASSWORD_HASH = _hash_password(os.environ.get('ADMIN_PASSWORD', 'change-me'))

_USERS: Dict[str, Dict[str, Any]] = {
    'admin': {
        'password_hash': _ADMIN_PASSWORD_HASH,
        'role': 'admin',
        'tenant': 'default',
        'active': True,
    },
}

_TENANTS: Dict[str, Dict[str, Any]] = {
    'default': {'name': 'Default Tenant', 'api_key': os.environ.get('DEFAULT_TENANT_API_KEY', '')},
}


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
    """Decorator: require the caller to have one of the specified roles."""
    def decorator(f):
        @wraps(f)
        @login_required
        def decorated(*args, **kwargs):
            caller_level = ROLE_HIERARCHY.get(g.role, 0)
            required_level = max(ROLE_HIERARCHY.get(r, 0) for r in required_roles)
            if caller_level < required_level:
                return jsonify({'error': f'Role {required_roles} required'}), 403
            return f(*args, **kwargs)
        return decorated
    return decorator


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
        return jsonify([
            {'username': u, 'role': d['role'], 'tenant': d['tenant'], 'active': d['active']}
            for u, d in _USERS.items()
        ])

    @app.route('/api/auth/users', methods=['POST'])
    @role_required('admin')
    def create_user():
        data = request.get_json(silent=True) or {}
        username = data.get('username', '').strip()
        password = data.get('password', '')
        role = data.get('role', 'read-only')
        tenant = data.get('tenant', g.tenant)

        if not username or not password:
            return jsonify({'error': 'username and password required'}), 400
        if username in _USERS:
            return jsonify({'error': 'User already exists'}), 409
        if role not in ROLES:
            return jsonify({'error': f'role must be one of {ROLES}'}), 400

        _USERS[username] = {
            'password_hash': _hash_password(password),
            'role': role,
            'tenant': tenant,
            'active': True,
        }
        return jsonify({'created': username, 'role': role, 'tenant': tenant}), 201

    @app.route('/api/auth/users/<username>', methods=['DELETE'])
    @role_required('admin')
    def deactivate_user(username):
        if username not in _USERS:
            return jsonify({'error': 'User not found'}), 404
        if username == g.user:
            return jsonify({'error': 'Cannot deactivate yourself'}), 400
        _USERS[username]['active'] = False
        return jsonify({'deactivated': username})

    @app.route('/api/auth/tenants', methods=['POST'])
    @role_required('admin')
    def create_tenant():
        data = request.get_json(silent=True) or {}
        tenant_id = data.get('tenant_id', '').strip()
        name = data.get('name', tenant_id)
        if not tenant_id:
            return jsonify({'error': 'tenant_id required'}), 400
        if tenant_id in _TENANTS:
            return jsonify({'error': 'Tenant already exists'}), 409
        api_key = secrets.token_hex(32)
        _TENANTS[tenant_id] = {'name': name, 'api_key': api_key}
        return jsonify({'tenant_id': tenant_id, 'api_key': api_key}), 201
