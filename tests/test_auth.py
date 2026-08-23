"""Tests for auth.py's module-level account functions (Phase B extraction),
plus the login_required/role_required decorator branches (Task 9 of the
test-coverage-improvement-plan) that actually gate every protected endpoint
in the API (see Tasks 6-8's tests/test_registry_routes.py, test_jobs.py,
test_audit.py).
"""

import os
import time

import jwt
import pytest
from flask import jsonify

import medical_data_validator.auth as auth


@pytest.fixture(autouse=True)
def _clean_users_and_tenants():
    """Each test gets a snapshot/restore of the in-memory stores."""
    users_before = dict(auth._USERS)
    tenants_before = dict(auth._TENANTS)
    yield
    auth._USERS.clear()
    auth._USERS.update(users_before)
    auth._TENANTS.clear()
    auth._TENANTS.update(tenants_before)


def test_list_user_accounts_includes_seeded_admin():
    users = auth.list_user_accounts()
    assert any(u['username'] == 'admin' for u in users)


def test_create_user_account_then_appears_in_list():
    auth.create_user_account('alice', 'password123', role='read-only', tenant='default')
    usernames = [u['username'] for u in auth.list_user_accounts()]
    assert 'alice' in usernames


def test_create_user_account_rejects_duplicate():
    auth.create_user_account('bob', 'password123')
    with pytest.raises(ValueError, match="already exists"):
        auth.create_user_account('bob', 'password123')


def test_create_user_account_rejects_bad_role():
    with pytest.raises(ValueError, match="role must be one of"):
        auth.create_user_account('carol', 'password123', role='superuser')


def test_deactivate_user_account_sets_inactive():
    auth.create_user_account('dave', 'password123')
    auth.deactivate_user_account('dave')
    assert auth._USERS['dave']['active'] is False


def test_deactivate_user_account_missing_user_raises():
    with pytest.raises(ValueError, match="not found"):
        auth.deactivate_user_account('nobody')


def test_create_tenant_account_then_stored():
    result = auth.create_tenant_account('hospital-a', 'Hospital A')
    assert result['tenant_id'] == 'hospital-a'
    assert 'api_key' in result
    assert auth._TENANTS['hospital-a']['name'] == 'Hospital A'


def test_create_tenant_account_rejects_duplicate():
    auth.create_tenant_account('dup-tenant')
    with pytest.raises(ValueError, match="already exists"):
        auth.create_tenant_account('dup-tenant')


from medical_data_validator.dashboard.app import create_dashboard_app


@pytest.fixture(scope="module")
def client():
    app = create_dashboard_app()
    app.config['TESTING'] = True
    with app.test_client() as client:
        yield client


def _admin_token(client):
    resp = client.post('/api/auth/token', json={
        'username': 'admin',
        'password': os.environ.get('ADMIN_PASSWORD', 'change-me'),
    })
    return resp.get_json()['access_token']


def test_route_create_user_still_returns_201(client):
    token = _admin_token(client)
    resp = client.post('/api/auth/users', json={'username': 'route-test-user', 'password': 'pw123456'},
                        headers={'Authorization': f'Bearer {token}'})
    assert resp.status_code == 201


def test_route_create_duplicate_user_still_returns_409(client):
    token = _admin_token(client)
    client.post('/api/auth/users', json={'username': 'dup-route-user', 'password': 'pw123456'},
                headers={'Authorization': f'Bearer {token}'})
    resp = client.post('/api/auth/users', json={'username': 'dup-route-user', 'password': 'pw123456'},
                        headers={'Authorization': f'Bearer {token}'})
    assert resp.status_code == 409


# ── login_required / role_required decorator branches (Task 9) ───────────────
#
# All of these hit /api/auth/me (bare @login_required) or /api/auth/users
# (@role_required('admin')) through a real Flask test client -- no mocking of
# auth.py itself. Auxiliary users/tenants are created through the same public
# auth.py functions the routes themselves use.

def _token(client, username, password='password123'):
    resp = client.post('/api/auth/token', json={'username': username, 'password': password})
    assert resp.status_code == 200, resp.get_json()
    return resp.get_json()['access_token']


def _auth_header(token, api_key=None):
    headers = {'Authorization': f'Bearer {token}'}
    if api_key is not None:
        headers['X-API-Key'] = api_key
    return headers


class TestLoginRequiredNoToken:
    """login_required: no-token branch (~109-111) and _extract_token (~88-92)."""

    def test_missing_authorization_header_returns_401(self, client):
        resp = client.get('/api/auth/me')
        assert resp.status_code == 401
        assert resp.get_json()['error'] == 'Authentication required'

    def test_authorization_header_without_bearer_prefix_returns_401(self, client):
        """_extract_token only recognizes a 'Bearer ' prefix; anything else
        (e.g. a raw token, or a different scheme) must fall through to
        the no-token branch, exercising _extract_token's `return None` (~92)."""
        resp = client.get('/api/auth/me', headers={'Authorization': 'Token abcdef'})
        assert resp.status_code == 401
        assert resp.get_json()['error'] == 'Authentication required'

    def test_bare_bearer_prefix_with_empty_token_is_treated_as_no_token(self, client):
        """'Bearer ' with nothing after it decodes to an empty string, which
        is falsy, so login_required still reports no-token rather than
        attempting to decode an empty JWT."""
        resp = client.get('/api/auth/me', headers={'Authorization': 'Bearer '})
        assert resp.status_code == 401
        assert resp.get_json()['error'] == 'Authentication required'


class TestLoginRequiredBadToken:
    """login_required: expired/invalid-token branches (~113-117)."""

    def test_malformed_token_returns_401_invalid_token(self, client):
        resp = client.get('/api/auth/me', headers=_auth_header('not-a-real-jwt'))
        assert resp.status_code == 401
        assert resp.get_json()['error'] == 'Invalid token'

    def test_token_signed_with_wrong_secret_returns_401_invalid_token(self, client):
        bad_token = jwt.encode(
            {'sub': 'admin', 'role': 'admin', 'tenant': 'default',
             'iat': int(time.time()), 'exp': int(time.time()) + 3600},
            'not-the-real-secret-but-still-long-enough-to-avoid-warnings',
            algorithm=auth.JWT_ALGORITHM,
        )
        resp = client.get('/api/auth/me', headers=_auth_header(bad_token))
        assert resp.status_code == 401
        assert resp.get_json()['error'] == 'Invalid token'

    def test_expired_token_returns_401_token_expired(self, client):
        expired_token = jwt.encode(
            {'sub': 'admin', 'role': 'admin', 'tenant': 'default',
             'iat': int(time.time()) - 7200, 'exp': int(time.time()) - 3600},
            auth.JWT_SECRET, algorithm=auth.JWT_ALGORITHM,
        )
        resp = client.get('/api/auth/me', headers=_auth_header(expired_token))
        assert resp.status_code == 401
        assert resp.get_json()['error'] == 'Token expired'


class TestLoginRequiredInactiveOrUnknownUser:
    """login_required: inactive-user / unknown-user branch (~119-122)."""

    def test_deactivated_user_valid_token_returns_401(self, client):
        """A token issued while the user was active must stop working the
        instant the account is deactivated: login_required re-checks
        `user.get('active')` on every request rather than trusting the JWT."""
        auth.create_user_account('auth-inactive-user', 'password123', role='read-only')
        token = _token(client, 'auth-inactive-user')

        # Sanity: token works before deactivation.
        ok_resp = client.get('/api/auth/me', headers=_auth_header(token))
        assert ok_resp.status_code == 200

        auth.deactivate_user_account('auth-inactive-user')
        resp = client.get('/api/auth/me', headers=_auth_header(token))
        assert resp.status_code == 401
        assert resp.get_json()['error'] == 'User not found or inactive'

    def test_token_for_deleted_unknown_user_returns_401(self, client):
        """A syntactically valid, correctly-signed token for a username that
        no longer exists in _USERS must be rejected (the `not user` half of
        the `if not user or not user.get('active')` condition)."""
        token = auth.create_token('no-such-user-at-all', 'admin', 'default')
        resp = client.get('/api/auth/me', headers=_auth_header(token))
        assert resp.status_code == 401
        assert resp.get_json()['error'] == 'User not found or inactive'


class TestExtractTenantAndApiKeyMismatch:
    """_extract_tenant (~95-102) and login_required's API-key-tenant-mismatch
    branch (~128-131)."""

    def test_matching_api_key_for_own_tenant_is_allowed(self, client):
        """X-API-Key resolving to the caller's own tenant must not be
        treated as a mismatch (exercises the loop's match branch, ~99-101,
        returning the matched tenant_id via hmac.compare_digest)."""
        tenant = auth.create_tenant_account('auth-tenant-match')
        auth.create_user_account(
            'auth-tenant-match-user', 'password123', role='read-only', tenant='auth-tenant-match',
        )
        token = _token(client, 'auth-tenant-match-user')
        resp = client.get('/api/auth/me', headers=_auth_header(token, api_key=tenant['api_key']))
        assert resp.status_code == 200
        assert resp.get_json()['tenant'] == 'auth-tenant-match'

    def test_non_admin_with_mismatched_api_key_tenant_returns_403(self, client):
        """A non-admin whose JWT tenant differs from the tenant resolved from
        X-API-Key must be rejected -- the API key can only narrow access,
        never let a caller reach into another tenant (~128-131)."""
        other_tenant = auth.create_tenant_account('auth-tenant-other')
        auth.create_user_account(
            'auth-tenant-mismatch-user', 'password123', role='data-steward', tenant='default',
        )
        token = _token(client, 'auth-tenant-mismatch-user')
        resp = client.get('/api/auth/me', headers=_auth_header(token, api_key=other_tenant['api_key']))
        assert resp.status_code == 403
        assert resp.get_json()['error'] == 'API key tenant mismatch'

    def test_admin_with_mismatched_api_key_tenant_is_never_blocked(self, client):
        """The mismatch check explicitly excludes admins (`g.role != 'admin'`)
        -- an admin's API key never narrows or blocks them."""
        other_tenant = auth.create_tenant_account('auth-tenant-other-admin')
        token = _admin_token(client)
        resp = client.get('/api/auth/me', headers=_auth_header(token, api_key=other_tenant['api_key']))
        assert resp.status_code == 200

    def test_unrecognized_api_key_is_ignored_not_treated_as_mismatch(self, client):
        """An X-API-Key that doesn't match any known tenant makes
        _extract_tenant's loop run to completion without matching (covering
        the no-match path through ~99-101), returning None -- which must
        not trigger the mismatch branch."""
        auth.create_user_account(
            'auth-unknown-apikey-user', 'password123', role='read-only', tenant='default',
        )
        token = _token(client, 'auth-unknown-apikey-user')
        resp = client.get('/api/auth/me', headers=_auth_header(token, api_key='totally-bogus-key'))
        assert resp.status_code == 200


class TestRoleRequiredInsufficientRole:
    """role_required's insufficient-role 403 branch (~143-146)."""

    def test_read_only_user_forbidden_from_admin_only_route(self, client):
        auth.create_user_account('auth-readonly-role-user', 'password123', role='read-only')
        token = _token(client, 'auth-readonly-role-user')
        resp = client.get('/api/auth/users', headers=_auth_header(token))
        assert resp.status_code == 403

    def test_admin_role_can_reach_admin_only_route(self, client):
        token = _admin_token(client)
        resp = client.get('/api/auth/users', headers=_auth_header(token))
        assert resp.status_code == 200


class TestVerifyPasswordMalformedHash:
    """_verify_password's malformed-hash except branch (~43-49)."""

    def test_verify_password_returns_false_for_hash_missing_separator(self):
        assert auth._verify_password('anything', 'no-colon-in-this-string') is False

    def test_verify_password_returns_false_for_empty_stored_hash(self):
        assert auth._verify_password('anything', '') is False

    def test_verify_password_true_for_correctly_hashed_password(self):
        stored = auth._hash_password('correct-horse-battery-staple')
        assert auth._verify_password('correct-horse-battery-staple', stored) is True

    def test_verify_password_false_for_wrong_password_against_valid_hash(self):
        stored = auth._hash_password('correct-horse-battery-staple')
        assert auth._verify_password('wrong-password', stored) is False

    def test_token_route_with_malformed_stored_hash_returns_401_not_500(self, client):
        """End-to-end: a user record with a corrupted password_hash must
        fail login cleanly (401) rather than raising -- proving the except
        branch is what protects the /api/auth/token route, not just a unit
        of _verify_password in isolation."""
        auth._USERS['auth-corrupted-hash-user'] = {
            'password_hash': 'this-has-no-colon-separator',
            'role': 'read-only',
            'tenant': 'default',
            'active': True,
        }
        resp = client.post('/api/auth/token', json={
            'username': 'auth-corrupted-hash-user',
            'password': 'whatever',
        })
        assert resp.status_code == 401
        assert resp.get_json()['error'] == 'Invalid credentials'


class TestRoleRequiredMultiRoleFix:
    """Regression test for a bug that was found and fixed in this same
    test-coverage-improvement effort, independently discovered three times
    across tests/test_registry_routes.py (create_dataset_endpoint,
    update_dataset_endpoint, record_run_endpoint), tests/test_job_routes.py,
    and this file -- all exercising `@role_required('data-steward',
    'admin')`-decorated REST endpoints and finding data-steward callers
    incorrectly rejected.

    Root cause, in role_required() itself (auth.py ~137-149), was:

        caller_level = ROLE_HIERARCHY.get(g.role, 0)
        required_level = max(ROLE_HIERARCHY.get(r, 0) for r in required_roles)
        if caller_level < required_level:
            return 403

    `max()` picked the HIGHEST-ranked named role as the bar every caller had
    to clear, even though the decorator's own docstring says "require the
    caller to have one of the specified roles" (i.e. the caller should only
    need to clear the LOWEST named role). As a result,
    `role_required('data-steward', 'admin')` was, in practice,
    indistinguishable from `role_required('admin')` alone: a data-steward
    (level 2) could never satisfy required_level = max(2, 3) = 3.

    The fix changes `max()` to `min()`, so required_level = min(2, 3) = 2,
    letting both data-steward and admin through while still correctly
    rejecting read-only (level 1).

    This test reproduces the (now fixed) scenario directly against
    role_required() with a throwaway dummy view, independent of any
    specific downstream route, so the fix has one authoritative
    source-level regression test rather than living only inside three
    unrelated REST API test files.

    Note a second, related footgun the min()-based fix introduces on its
    own: ROLE_HIERARCHY.get(r, 0) resolves an unknown/typo'd role name to
    level 0, and min() propagates that 0 straight through -- silently
    admitting every authenticated caller. role_required() now validates its
    role names eagerly (at decoration time) to guard against this; see
    test_role_required_raises_on_unknown_role_name below.
    """

    def test_role_required_multi_role_decorator_allows_any_named_role(self):
        # A small standalone Flask app (per this task's own instructions:
        # "a small dummy route you register on a test app, if that's
        # cleaner for isolating a specific decorator branch"), rather than
        # bolting a route onto the module-scoped shared `client` fixture's
        # app after it has already handled requests (Flask forbids that).
        from flask import Flask

        dummy_app = Flask(__name__)

        @dummy_app.route('/dummy-multi-role')
        @auth.role_required('data-steward', 'admin')
        def _dummy_multi_role_view():
            return jsonify({'ok': True})

        auth.create_user_account('auth-bug-steward-user', 'password123', role='data-steward')
        steward_token = auth.create_token('auth-bug-steward-user', 'data-steward', 'default')

        auth.create_user_account('auth-bug-readonly-user', 'password123', role='read-only')
        readonly_token = auth.create_token('auth-bug-readonly-user', 'read-only', 'default')

        with dummy_app.test_client() as dummy_client:
            steward_resp = dummy_client.get('/dummy-multi-role', headers=_auth_header(steward_token))
            readonly_resp = dummy_client.get('/dummy-multi-role', headers=_auth_header(readonly_token))

        # FIXED: a data-steward, explicitly named as an allowed role, is now
        # accepted because role_required() computes the *min* required
        # level (data-steward's) instead of the *max* (admin's).
        assert steward_resp.status_code == 200
        assert steward_resp.get_json() == {'ok': True}

        # read-only (level 1) still correctly fails: min(2, 3) = 2 is still
        # above read-only's level, so the fix doesn't over-widen access.
        assert readonly_resp.status_code == 403

    def test_role_required_raises_on_unknown_role_name(self):
        """min()'s own footgun: ROLE_HIERARCHY.get(r, 0) resolves an unknown
        role name to level 0, and min() would propagate that 0 straight
        through as required_level -- meaning a typo'd role name (e.g.
        'data-stewart' instead of 'data-steward') would silently admit
        EVERY authenticated caller, including read-only. (The old max()
        based check happened to fail closed on the same typo, admitting
        only admin -- so this footgun is new with the min() fix and must be
        guarded against explicitly.)

        role_required() must instead validate its role names eagerly, at
        decoration time (i.e. when the module defining the route is
        imported), so a typo raises immediately at startup rather than
        shipping a silently-too-permissive endpoint that no test would
        catch at runtime."""
        with pytest.raises(ValueError, match="unknown role"):
            auth.role_required('admin', 'data-stewart')  # typo, not a real role

    def test_role_required_accepts_all_real_role_names(self):
        """Sanity check that the new validation doesn't reject legitimate
        role names -- every real role in ROLES/ROLE_HIERARCHY, alone or in
        combination, must decorate cleanly without raising."""
        for role in auth.ROLES:
            auth.role_required(role)  # must not raise
        auth.role_required('data-steward', 'admin')  # must not raise


class TestUserTenantStoreSurvivesConnectionReset:
    """Regression coverage for the bug this SQLite migration fixes: a plain
    in-memory _USERS/_TENANTS dict was invisible across Gunicorn's separate
    worker processes, so a user or tenant created on one worker didn't
    exist as far as another was concerned. Each worker process only ever
    opens its own sqlite3.Connection once (auth._get_conn() caches it in
    `auth._conn`), so dropping and recreating that connection mid-test
    stands in for "a different worker process reads the same file"."""

    def test_user_created_before_a_connection_reset_is_still_visible_after(self):
        auth.create_user_account('persist-check-user', 'password123', role='read-only')

        auth._conn.close()
        auth._conn = None

        assert 'persist-check-user' in auth._USERS
        assert auth._USERS['persist-check-user']['role'] == 'read-only'

    def test_tenant_created_before_a_connection_reset_is_still_visible_after(self):
        auth.create_tenant_account('persist-check-tenant', 'Persistence Check')

        auth._conn.close()
        auth._conn = None

        assert 'persist-check-tenant' in auth._TENANTS
        assert auth._TENANTS['persist-check-tenant']['name'] == 'Persistence Check'
