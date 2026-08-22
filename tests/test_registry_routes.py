"""Characterization tests for the /api/registry/* REST API in
medical_data_validator/registry.py's register_registry_routes (0% covered
before this file).

Covers all 7 endpoints:
  GET    /api/registry/datasets                        (list_datasets_endpoint)
  POST   /api/registry/datasets                         (create_dataset_endpoint)
  GET    /api/registry/datasets/<id>                    (get_dataset_endpoint)
  PATCH  /api/registry/datasets/<id>                    (update_dataset_endpoint)
  DELETE /api/registry/datasets/<id>                    (delete_dataset_endpoint)
  GET    /api/registry/datasets/<id>/history            (get_history_endpoint)
  POST   /api/registry/datasets/<id>/runs               (record_run_endpoint)

Setup patterns reused from other test files in this suite:
- Isolated registry DB: temp-file + REGISTRY_DB_PATH swap + _conn reset,
  same idea as tests/test_dash_registry_page.py's `_isolated_registry_db`
  fixture.
- JWT token acquisition via /api/auth/token, same as tests/test_auth.py's
  `_admin_token(client)` helper.
- create_dashboard_app() + app.test_client(), module-scoped client, same as
  tests/test_auth.py and tests/test_flask_api_v12_endpoints.py.

DISCOVERED BUG -- role_required() with multiple roles collapses to the
HIGHEST role's level, not "any of these roles" (see auth.py:137-149):

    caller_level = ROLE_HIERARCHY.get(g.role, 0)
    required_level = max(ROLE_HIERARCHY.get(r, 0) for r in required_roles)
    if caller_level < required_level:
        return 403

For `@role_required('data-steward', 'admin')` (used on create_dataset_endpoint,
update_dataset_endpoint, and record_run_endpoint below, and also in jobs.py
and audit.py -- out of scope here), required_level = max(2, 3) = 3, i.e.
admin's level. A data-steward (level 2) can therefore NEVER satisfy this
check, despite being explicitly named as an allowed role. In effect,
`role_required('data-steward', 'admin')` behaves identically to
`role_required('admin')` alone. This is a real, previously-unexercised bug:
every one of these "data-steward or admin" endpoints is actually
admin-only in production.

This is documented (not fixed) per the plan's guidance, and it reshapes what
"happy path" means for the affected endpoints below: since only admin can
ever pass the decorator, admin is used for their happy-path tests, and a
dedicated test on each affected endpoint demonstrates a data-steward being
incorrectly rejected.

A second, related consequence: because only admin can reach
update_dataset_endpoint and record_run_endpoint, their internal
`g.role != 'admin' and ds.get('tenant') != g.tenant` cross-tenant check is
DEAD CODE in the current build -- admin always satisfies `g.role == 'admin'`
and skips it, and no non-admin caller can even reach the decorator body to
trigger it. This is noted below rather than faked with an unreachable test.
"""

import os

import pytest

import medical_data_validator.registry as registry
import medical_data_validator.auth as auth
from medical_data_validator.dashboard.app import create_dashboard_app


@pytest.fixture(autouse=True)
def _isolated_registry_db(tmp_path):
    tf = tmp_path / "registry_routes_test.db"
    old_path = registry.REGISTRY_DB_PATH
    registry.REGISTRY_DB_PATH = str(tf)
    if registry._conn is not None:
        registry._conn.close()
        registry._conn = None
    yield
    registry.REGISTRY_DB_PATH = old_path
    if registry._conn is not None:
        registry._conn.close()
        registry._conn = None


@pytest.fixture(scope="module")
def client():
    app = create_dashboard_app()
    app.config['TESTING'] = True
    with app.test_client() as client:
        yield client


@pytest.fixture(scope="module", autouse=True)
def _seed_non_admin_users():
    """Two data-steward users in different tenants, plus a read-only user,
    so tenant-isolation and role-gating can both be exercised with real
    non-admin callers. Module-scoped since auth._USERS is a process-wide
    in-memory store shared by every test file in the run; names are unique
    enough not to collide with other test modules' seeded users."""
    created = []
    for username, role, tenant in [
        ('registry-steward-a', 'data-steward', 'registry-tenant-a'),
        ('registry-steward-b', 'data-steward', 'registry-tenant-b'),
        ('registry-readonly-a', 'read-only', 'registry-tenant-a'),
    ]:
        if username not in auth._USERS:
            auth.create_user_account(username, 'password123', role=role, tenant=tenant)
            created.append(username)
    yield
    for username in created:
        auth._USERS.pop(username, None)


def _token(client, username, password='password123'):
    resp = client.post('/api/auth/token', json={'username': username, 'password': password})
    assert resp.status_code == 200, resp.get_json()
    return resp.get_json()['access_token']


def _auth_header(token):
    return {'Authorization': f'Bearer {token}'}


@pytest.fixture()
def admin_token(client):
    return _token(client, 'admin', os.environ.get('ADMIN_PASSWORD', 'change-me'))


@pytest.fixture()
def steward_a_token(client):
    return _token(client, 'registry-steward-a')


@pytest.fixture()
def steward_b_token(client):
    return _token(client, 'registry-steward-b')


@pytest.fixture()
def readonly_a_token(client):
    return _token(client, 'registry-readonly-a')


def _create_via_api(client, token, name, **extra):
    body = {'name': name}
    body.update(extra)
    return client.post('/api/registry/datasets', json=body, headers=_auth_header(token))


def _seed(name, tenant, **kw):
    """Seed a dataset directly through the registry module (bypassing HTTP),
    so tests of GET/PATCH/DELETE/history/record-run aren't entangled with
    create_dataset_endpoint's own role gating (see the role_required bug
    documented at module level)."""
    return registry.register_dataset(name, tenant=tenant, **kw)


# ---------------------------------------------------------------------------
# POST /api/registry/datasets -- create_dataset_endpoint
# ---------------------------------------------------------------------------

class TestCreateDataset:
    def test_happy_path_admin_creates_dataset_defaults_tenant(self, client, admin_token):
        resp = _create_via_api(client, admin_token, 'ds-create-happy',
                                description='a dataset', tags=['x', 'y'])
        assert resp.status_code == 201
        body = resp.get_json()
        assert body['name'] == 'ds-create-happy'
        assert body['tenant'] == 'default'  # admin's own tenant, since none was supplied
        assert body['description'] == 'a dataset'
        assert body['tags'] == ['x', 'y']
        assert 'id' in body

    def test_missing_name_returns_400(self, client, admin_token):
        resp = client.post('/api/registry/datasets', json={}, headers=_auth_header(admin_token))
        assert resp.status_code == 400
        assert 'name' in resp.get_json()['error'].lower()

    def test_blank_name_returns_400(self, client, admin_token):
        resp = _create_via_api(client, admin_token, '   ')
        assert resp.status_code == 400

    def test_duplicate_name_and_tenant_returns_409(self, client, admin_token):
        _create_via_api(client, admin_token, 'ds-dup')
        resp = _create_via_api(client, admin_token, 'ds-dup')
        assert resp.status_code == 409
        assert 'already exists' in resp.get_json()['error']

    def test_admin_can_create_for_explicit_tenant(self, client, admin_token):
        resp = _create_via_api(client, admin_token, 'ds-admin-explicit-tenant',
                                tenant='registry-tenant-b')
        assert resp.status_code == 201
        assert resp.get_json()['tenant'] == 'registry-tenant-b'

    def test_no_token_unauthorized(self, client):
        resp = client.post('/api/registry/datasets', json={'name': 'ds-no-auth'})
        assert resp.status_code == 401

    def test_BUG_role_required_blocks_named_data_steward_role(self, client, steward_a_token):
        """DISCOVERED BUG (documented, not fixed): the decorator on this
        route is `@role_required('data-steward', 'admin')`, explicitly
        naming data-steward as an allowed role, but role_required()'s
        max()-based level check makes it admin-only in practice (see module
        docstring). A data-steward is incorrectly forbidden from creating a
        dataset at all -- even one scoped to their own tenant."""
        resp = _create_via_api(client, steward_a_token, 'ds-steward-blocked')
        assert resp.status_code == 403

    def test_read_only_role_forbidden(self, client, readonly_a_token):
        resp = _create_via_api(client, readonly_a_token, 'ds-readonly-attempt')
        assert resp.status_code == 403


# ---------------------------------------------------------------------------
# GET /api/registry/datasets -- list_datasets_endpoint (login_required only;
# unaffected by the role_required bug above)
# ---------------------------------------------------------------------------

class TestListDatasets:
    def test_non_admin_only_sees_own_tenant(self, client, steward_a_token):
        _seed('list-a-1', 'registry-tenant-a')
        _seed('list-a-2', 'registry-tenant-a')
        _seed('list-b-1', 'registry-tenant-b')

        resp = client.get('/api/registry/datasets', headers=_auth_header(steward_a_token))
        assert resp.status_code == 200
        body = resp.get_json()
        names = {d['name'] for d in body['datasets']}
        assert 'list-a-1' in names
        assert 'list-a-2' in names
        assert 'list-b-1' not in names
        assert body['total'] == len(body['datasets'])

    def test_non_admin_tenant_query_param_is_ignored(self, client, steward_a_token):
        """A non-admin cannot use ?tenant= to peek at another tenant's list --
        list_datasets_endpoint correctly forces tenant=g.tenant for
        non-admins. (Contrast with create_dataset_endpoint's missing clamp,
        documented above.)"""
        _seed('list-b-only', 'registry-tenant-b')
        resp = client.get('/api/registry/datasets?tenant=registry-tenant-b',
                           headers=_auth_header(steward_a_token))
        assert resp.status_code == 200
        names = {d['name'] for d in resp.get_json()['datasets']}
        assert 'list-b-only' not in names

    def test_admin_can_filter_by_tenant_query_param(self, client, admin_token):
        _seed('list-admin-view-b', 'registry-tenant-b')
        resp = client.get('/api/registry/datasets?tenant=registry-tenant-b',
                           headers=_auth_header(admin_token))
        assert resp.status_code == 200
        names = {d['name'] for d in resp.get_json()['datasets']}
        assert 'list-admin-view-b' in names

    def test_admin_without_tenant_param_defaults_to_own_tenant(self, client, admin_token):
        _seed('list-admin-own-tenant', 'default')
        _seed('list-admin-other-tenant', 'registry-tenant-b')
        resp = client.get('/api/registry/datasets', headers=_auth_header(admin_token))
        assert resp.status_code == 200
        names = {d['name'] for d in resp.get_json()['datasets']}
        assert 'list-admin-own-tenant' in names
        assert 'list-admin-other-tenant' not in names

    def test_tag_filter(self, client, steward_a_token):
        _seed('list-tagged', 'registry-tenant-a', tags=['special-tag'])
        _seed('list-untagged', 'registry-tenant-a')
        resp = client.get('/api/registry/datasets?tag=special-tag',
                           headers=_auth_header(steward_a_token))
        assert resp.status_code == 200
        names = {d['name'] for d in resp.get_json()['datasets']}
        assert 'list-tagged' in names
        assert 'list-untagged' not in names

    def test_no_token_unauthorized(self, client):
        resp = client.get('/api/registry/datasets')
        assert resp.status_code == 401


# ---------------------------------------------------------------------------
# GET /api/registry/datasets/<id> -- get_dataset_endpoint (login_required
# only; unaffected by the role_required bug)
# ---------------------------------------------------------------------------

class TestGetDataset:
    def test_happy_path_owner_can_view(self, client, steward_a_token):
        created = _seed('get-happy', 'registry-tenant-a')
        resp = client.get(f"/api/registry/datasets/{created['id']}",
                           headers=_auth_header(steward_a_token))
        assert resp.status_code == 200
        assert resp.get_json()['name'] == 'get-happy'

    def test_not_found_returns_404(self, client, steward_a_token):
        resp = client.get('/api/registry/datasets/does-not-exist',
                           headers=_auth_header(steward_a_token))
        assert resp.status_code == 404
        assert 'not found' in resp.get_json()['error'].lower()

    def test_cross_tenant_non_admin_forbidden(self, client, steward_a_token):
        other = _seed('get-cross-tenant', 'registry-tenant-b')
        resp = client.get(f"/api/registry/datasets/{other['id']}",
                           headers=_auth_header(steward_a_token))
        assert resp.status_code == 403
        assert resp.get_json()['error'] == 'Forbidden'

    def test_admin_can_view_any_tenant(self, client, admin_token):
        other = _seed('get-admin-view', 'registry-tenant-b')
        resp = client.get(f"/api/registry/datasets/{other['id']}",
                           headers=_auth_header(admin_token))
        assert resp.status_code == 200
        assert resp.get_json()['name'] == 'get-admin-view'

    def test_readonly_role_can_view_own_tenant(self, client, readonly_a_token):
        """get_dataset_endpoint only requires login_required, not a specific
        role -- a read-only user in the same tenant can view (correctly,
        since this endpoint isn't role-gated at all)."""
        created = _seed('get-readonly-ok', 'registry-tenant-a')
        resp = client.get(f"/api/registry/datasets/{created['id']}",
                           headers=_auth_header(readonly_a_token))
        assert resp.status_code == 200

    def test_no_token_unauthorized(self, client):
        created = _seed('get-no-auth', 'registry-tenant-a')
        resp = client.get(f"/api/registry/datasets/{created['id']}")
        assert resp.status_code == 401


# ---------------------------------------------------------------------------
# PATCH /api/registry/datasets/<id> -- update_dataset_endpoint
# ---------------------------------------------------------------------------

class TestUpdateDataset:
    def test_happy_path_updates_description_and_tags(self, client, admin_token):
        created = _seed('update-happy', 'default', description='old')
        resp = client.patch(f"/api/registry/datasets/{created['id']}",
                             json={'description': 'new', 'tags': ['fresh']},
                             headers=_auth_header(admin_token))
        assert resp.status_code == 200
        body = resp.get_json()
        assert body['description'] == 'new'
        assert body['tags'] == ['fresh']

    def test_not_found_returns_404(self, client, admin_token):
        resp = client.patch('/api/registry/datasets/does-not-exist',
                             json={'description': 'x'},
                             headers=_auth_header(admin_token))
        assert resp.status_code == 404

    def test_admin_can_update_any_tenant(self, client, admin_token):
        other = _seed('update-admin', 'registry-tenant-b')
        resp = client.patch(f"/api/registry/datasets/{other['id']}",
                             json={'description': 'admin-updated'},
                             headers=_auth_header(admin_token))
        assert resp.status_code == 200
        assert resp.get_json()['description'] == 'admin-updated'

    def test_read_only_role_forbidden(self, client, readonly_a_token):
        created = _seed('update-readonly-attempt', 'registry-tenant-a')
        resp = client.patch(f"/api/registry/datasets/{created['id']}",
                             json={'description': 'nope'},
                             headers=_auth_header(readonly_a_token))
        assert resp.status_code == 403

    def test_BUG_role_required_blocks_data_steward_even_on_own_dataset(self, client, steward_a_token):
        """DISCOVERED BUG (documented, not fixed): same role_required() flaw
        as create_dataset_endpoint. A data-steward cannot update even their
        OWN tenant's dataset, despite 'data-steward' being named explicitly
        in @role_required('data-steward', 'admin'). Consequence: because
        only admin can ever pass this decorator, and admin always bypasses
        the internal `ds.get('tenant') != g.tenant` check, that internal
        cross-tenant-403 branch is dead code in the current build -- no
        caller can reach it. Not tested here for that reason."""
        created = _seed('update-steward-own', 'registry-tenant-a', description='original')
        resp = client.patch(f"/api/registry/datasets/{created['id']}",
                             json={'description': 'attempted-update'},
                             headers=_auth_header(steward_a_token))
        assert resp.status_code == 403
        unchanged = registry.get_dataset(created['id'])
        assert unchanged['description'] == 'original'


# ---------------------------------------------------------------------------
# DELETE /api/registry/datasets/<id> -- delete_dataset_endpoint
# (role_required('admin') -- a single role, so the max()-collapse bug above
# has no effect here: admin-only is exactly what's intended and enforced.)
# ---------------------------------------------------------------------------

class TestDeleteDataset:
    def test_happy_path_admin_deletes(self, client, admin_token):
        created = _seed('delete-happy', 'default')
        resp = client.delete(f"/api/registry/datasets/{created['id']}",
                              headers=_auth_header(admin_token))
        assert resp.status_code == 200
        assert resp.get_json()['deleted'] == created['id']
        assert registry.get_dataset(created['id']) is None

    def test_not_found_returns_404(self, client, admin_token):
        resp = client.delete('/api/registry/datasets/does-not-exist',
                              headers=_auth_header(admin_token))
        assert resp.status_code == 404

    def test_non_admin_role_forbidden_even_for_own_dataset(self, client, steward_a_token):
        """This is intended behavior, not a bug: the decorator names only
        'admin', so a data-steward is correctly forbidden from deleting even
        their own tenant's dataset."""
        created = _seed('delete-non-admin-own', 'registry-tenant-a')
        resp = client.delete(f"/api/registry/datasets/{created['id']}",
                              headers=_auth_header(steward_a_token))
        assert resp.status_code == 403
        assert registry.get_dataset(created['id']) is not None


# ---------------------------------------------------------------------------
# GET /api/registry/datasets/<id>/history -- get_history_endpoint
# (login_required only; unaffected by the role_required bug)
# ---------------------------------------------------------------------------

class TestGetHistory:
    def test_happy_path_returns_recorded_runs(self, client, steward_a_token):
        created = _seed('history-happy', 'registry-tenant-a')
        registry.record_run(created['id'], is_valid=True, error_count=0, warning_count=1)
        registry.record_run(created['id'], is_valid=False, error_count=3, warning_count=0)

        resp = client.get(f"/api/registry/datasets/{created['id']}/history",
                           headers=_auth_header(steward_a_token))
        assert resp.status_code == 200
        body = resp.get_json()
        assert body['total'] == 2
        assert len(body['runs']) == 2
        error_counts = {r['error_count'] for r in body['runs']}
        assert error_counts == {0, 3}

    def test_not_found_returns_404(self, client, steward_a_token):
        resp = client.get('/api/registry/datasets/does-not-exist/history',
                           headers=_auth_header(steward_a_token))
        assert resp.status_code == 404

    def test_cross_tenant_non_admin_forbidden(self, client, steward_a_token):
        other = _seed('history-cross-tenant', 'registry-tenant-b')
        registry.record_run(other['id'], is_valid=True)
        resp = client.get(f"/api/registry/datasets/{other['id']}/history",
                           headers=_auth_header(steward_a_token))
        assert resp.status_code == 403

    def test_admin_can_view_any_tenant_history(self, client, admin_token):
        other = _seed('history-admin', 'registry-tenant-b')
        registry.record_run(other['id'], is_valid=True)
        resp = client.get(f"/api/registry/datasets/{other['id']}/history",
                           headers=_auth_header(admin_token))
        assert resp.status_code == 200
        assert resp.get_json()['total'] == 1


# ---------------------------------------------------------------------------
# POST /api/registry/datasets/<id>/runs -- record_run_endpoint
# ---------------------------------------------------------------------------

class TestRecordRun:
    def test_happy_path_records_run_and_appears_in_history(self, client, admin_token):
        created = _seed('record-run-happy', 'default')
        resp = client.post(f"/api/registry/datasets/{created['id']}/runs",
                            json={'audit_id': 'audit-123', 'is_valid': False,
                                  'error_count': 2, 'warning_count': 5},
                            headers=_auth_header(admin_token))
        assert resp.status_code == 201
        run_id = resp.get_json()['run_id']
        assert run_id

        history = registry.get_run_history(created['id'])
        assert len(history) == 1
        assert history[0]['id'] == run_id
        assert history[0]['audit_id'] == 'audit-123'
        assert history[0]['is_valid'] == 0
        assert history[0]['error_count'] == 2
        assert history[0]['warning_count'] == 5

    def test_defaults_when_body_omits_counts(self, client, admin_token):
        created = _seed('record-run-defaults', 'default')
        resp = client.post(f"/api/registry/datasets/{created['id']}/runs",
                            json={}, headers=_auth_header(admin_token))
        assert resp.status_code == 201
        history = registry.get_run_history(created['id'])
        assert history[0]['error_count'] == 0
        assert history[0]['warning_count'] == 0
        assert history[0]['is_valid'] is None

    def test_not_found_returns_404(self, client, admin_token):
        resp = client.post('/api/registry/datasets/does-not-exist/runs',
                            json={}, headers=_auth_header(admin_token))
        assert resp.status_code == 404

    def test_admin_can_record_run_for_any_tenant(self, client, admin_token):
        other = _seed('record-run-admin', 'registry-tenant-b')
        resp = client.post(f"/api/registry/datasets/{other['id']}/runs",
                            json={'is_valid': True}, headers=_auth_header(admin_token))
        assert resp.status_code == 201

    def test_read_only_role_forbidden(self, client, readonly_a_token):
        created = _seed('record-run-readonly', 'registry-tenant-a')
        resp = client.post(f"/api/registry/datasets/{created['id']}/runs",
                            json={}, headers=_auth_header(readonly_a_token))
        assert resp.status_code == 403

    def test_BUG_role_required_blocks_data_steward_even_on_own_dataset(self, client, steward_a_token):
        """DISCOVERED BUG (documented, not fixed): same role_required() flaw
        as create/update. A data-steward cannot record a run against even
        their OWN dataset. As with update_dataset_endpoint, this also makes
        the internal cross-tenant-403 check unreachable dead code (only
        admin ever reaches it, and admin always bypasses it)."""
        created = _seed('record-run-steward-own', 'registry-tenant-a')
        resp = client.post(f"/api/registry/datasets/{created['id']}/runs",
                            json={}, headers=_auth_header(steward_a_token))
        assert resp.status_code == 403
        assert registry.get_run_history(created['id']) == []
