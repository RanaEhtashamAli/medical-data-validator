"""Tests for auth.py's module-level account functions (Phase B extraction)."""

import pytest
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
    import os
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
