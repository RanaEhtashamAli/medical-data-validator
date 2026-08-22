"""Characterization tests for the /api/jobs REST API in
medical_data_validator/jobs.py's register_job_routes (0% covered before
this file).

Covers all 3 endpoints:
  POST /api/jobs          (submit_job_endpoint)
  GET  /api/jobs          (list_jobs_endpoint)
  GET  /api/jobs/<id>     (get_job_endpoint)

Explicitly SKIPPED per the plan: lines ~246-252 (`_celery_available()` —
celery isn't installed in this environment; forcing the ImportError-False
branch has near-zero value).

CRITICAL: known race condition (documented, not fixed) -----------------------
This project has a real, previously-reproduced race condition between
jobs.py's background worker thread and test-fixture DB teardown, which can
segfault the test process (reproduced 3/5 runs in an earlier session). Per
the plan's global constraint, all test setup here uses jobs.create_job()
directly (synchronous, no worker thread) instead of jobs.submit_job().

The ONE exception is `TestSubmitJob.test_happy_path_admin_submits_real_job`,
which exercises the actual submit endpoint end-to-end (the only way to prove
it really enqueues a job for background processing) using the same
"poll with a bounded retry loop" pattern already established in
tests/test_dash_jobs_page.py's test_submit_job_from_form_then_appears_in_list.
This is deliberately the ONLY new test in this file that starts a real async
job, to minimize the number of chances to trigger the race.

DISCOVERED BUG (documented, not fixed, already known from Task 6) --
role_required() with multiple roles collapses to the HIGHEST role's level,
not "any of these roles" (see auth.py:137-149). submit_job_endpoint is
decorated with `@role_required('data-steward', 'admin')` (jobs.py:267),
so required_level = max(2, 3) = 3, i.e. admin's level. A data-steward
(level 2) can therefore NEVER satisfy this check, despite being explicitly
named as an allowed role -- in effect this endpoint is admin-only in
production. This is exercised below (not re-litigated at length; see
tests/test_registry_routes.py's module docstring for the full analysis).
Because only admin can ever submit a job, admin is used for the happy-path
submit tests.
"""

import json
import os
import tempfile
import time

import pytest

import medical_data_validator.auth as auth
import medical_data_validator.jobs as jobs
from medical_data_validator.dashboard.app import create_dashboard_app


@pytest.fixture(autouse=True)
def _isolated_jobs_db():
    """Give each test its own fresh SQLite jobs DB and clean worker state
    (same pattern as tests/test_jobs.py and tests/test_report_routes.py)."""
    tf = tempfile.NamedTemporaryFile(suffix=".db", delete=False)
    tf.close()

    old_path = jobs.JOBS_DB_PATH
    jobs.JOBS_DB_PATH = tf.name
    if jobs._conn is not None:
        jobs._conn.close()
        jobs._conn = None
    jobs._worker_started = False

    yield

    if jobs._conn is not None:
        jobs._conn.close()
        jobs._conn = None
    jobs.JOBS_DB_PATH = old_path
    try:
        os.unlink(tf.name)
    except FileNotFoundError:
        pass


@pytest.fixture(scope="module")
def client():
    app = create_dashboard_app()
    app.config['TESTING'] = True
    with app.test_client() as client:
        yield client


@pytest.fixture(scope="module", autouse=True)
def _seed_non_admin_users():
    """A data-steward and a read-only user in one tenant, plus a second
    data-steward in a different tenant, so role-gating and tenant-isolation
    can both be exercised with real non-admin callers. Module-scoped since
    auth._USERS is a process-wide in-memory store shared by every test file
    in the run; names are unique to this module to avoid collisions."""
    created = []
    for username, role, tenant in [
        ('jobs-steward-a', 'data-steward', 'jobs-tenant-a'),
        ('jobs-steward-b', 'data-steward', 'jobs-tenant-b'),
        ('jobs-readonly-a', 'read-only', 'jobs-tenant-a'),
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
    return _token(client, 'jobs-steward-a')


@pytest.fixture()
def steward_b_token(client):
    return _token(client, 'jobs-steward-b')


@pytest.fixture()
def readonly_a_token(client):
    return _token(client, 'jobs-readonly-a')


def _wait_for_terminal(job_id, timeout=5.0):
    """Poll jobs.get_job() until the job leaves pending/running or timeout
    expires. Mirrors tests/test_dash_jobs_page.py's polling pattern."""
    deadline = time.time() + timeout
    job = jobs.get_job(job_id)
    while time.time() < deadline:
        job = jobs.get_job(job_id)
        if job and job['status'] not in ('pending', 'running'):
            return job
        time.sleep(0.05)
    return job


# ---------------------------------------------------------------------------
# POST /api/jobs -- submit_job_endpoint
# ---------------------------------------------------------------------------

class TestSubmitJob:
    def test_no_token_unauthorized(self, client):
        resp = client.post('/api/jobs', json={'job_type': 'validate', 'payload': {}})
        assert resp.status_code == 401

    def test_BUG_role_required_blocks_named_data_steward_role(self, client, steward_a_token):
        """DISCOVERED BUG (documented, not fixed): the decorator on this
        route is @role_required('data-steward', 'admin'), explicitly naming
        data-steward as an allowed role, but role_required()'s max()-based
        level check makes it admin-only in practice (see module docstring
        and auth.py:137-149). A data-steward is incorrectly forbidden from
        submitting any job at all."""
        resp = client.post(
            '/api/jobs',
            json={'job_type': 'validate', 'payload': {'data': {}}},
            headers=_auth_header(steward_a_token),
        )
        assert resp.status_code == 403

    def test_read_only_role_forbidden(self, client, readonly_a_token):
        resp = client.post(
            '/api/jobs',
            json={'job_type': 'validate', 'payload': {'data': {}}},
            headers=_auth_header(readonly_a_token),
        )
        assert resp.status_code == 403

    def test_missing_job_type_returns_400(self, client, admin_token):
        resp = client.post('/api/jobs', json={}, headers=_auth_header(admin_token))
        assert resp.status_code == 400
        assert 'job_type' in resp.get_json()['error']

    def test_invalid_job_type_returns_400(self, client, admin_token):
        resp = client.post(
            '/api/jobs',
            json={'job_type': 'not-a-real-type', 'payload': {}},
            headers=_auth_header(admin_token),
        )
        assert resp.status_code == 400
        assert 'job_type' in resp.get_json()['error']

    def test_non_dict_payload_returns_400(self, client, admin_token):
        resp = client.post(
            '/api/jobs',
            json={'job_type': 'validate', 'payload': ['not', 'a', 'dict']},
            headers=_auth_header(admin_token),
        )
        assert resp.status_code == 400
        assert 'payload' in resp.get_json()['error']

    def test_malformed_json_body_treated_as_missing_job_type(self, client, admin_token):
        # request.get_json(silent=True) returns None for unparseable JSON,
        # which the endpoint coerces to {} -- exercising that fallback.
        headers = dict(_auth_header(admin_token))
        headers['Content-Type'] = 'application/json'
        resp = client.post('/api/jobs', data='not json at all', headers=headers)
        assert resp.status_code == 400
        assert 'job_type' in resp.get_json()['error']

    def test_happy_path_admin_submits_real_job(self, client, admin_token):
        """The ONE test in this file that exercises the real async
        submit-and-process flow, per the plan's constraint to minimize real
        job submissions (every other submit test above 400s or 403s before
        reaching submit_job(), so none of them touch the worker thread).
        `payload` is deliberately omitted from the request body so this
        single submission also covers the endpoint's `data.get('payload', {})`
        defaulting branch. Confirms the endpoint actually enqueues a job
        that the background worker picks up and completes, and that
        tenant / username are stamped from the authenticated caller
        (g.tenant / g.user), not from the request body."""
        resp = client.post(
            '/api/jobs',
            json={'job_type': 'validate'},
            headers=_auth_header(admin_token),
        )
        assert resp.status_code == 202
        body = resp.get_json()
        assert body['job_type'] == 'validate'
        assert body['tenant'] == 'default'
        assert body['username'] == 'admin'
        assert body['payload'] == {}
        assert body['status'] in ('pending', 'running', 'completed')

        job = _wait_for_terminal(body['id'])
        assert job is not None
        assert job['status'] in ('completed', 'failed')
        assert job['job_type'] == 'validate'


# ---------------------------------------------------------------------------
# GET /api/jobs -- list_jobs_endpoint (login_required only; unaffected by
# the role_required bug)
# ---------------------------------------------------------------------------

class TestListJobs:
    def test_no_token_unauthorized(self, client):
        resp = client.get('/api/jobs')
        assert resp.status_code == 401

    def test_non_admin_only_sees_own_tenant(self, client, steward_a_token):
        jobs.create_job('validate', {'data': {}}, tenant='jobs-tenant-a', username='jobs-steward-a')
        jobs.create_job('validate', {'data': {}}, tenant='jobs-tenant-a', username='jobs-steward-a')
        jobs.create_job('validate', {'data': {}}, tenant='jobs-tenant-b', username='jobs-steward-b')

        resp = client.get('/api/jobs', headers=_auth_header(steward_a_token))
        assert resp.status_code == 200
        body = resp.get_json()
        tenants = {j['tenant'] for j in body['jobs']}
        assert tenants == {'jobs-tenant-a'}
        assert body['total'] == len(body['jobs']) == 2

    def test_non_admin_tenant_query_param_is_ignored(self, client, steward_a_token):
        jobs.create_job('validate', {'data': {}}, tenant='jobs-tenant-b', username='jobs-steward-b')
        resp = client.get('/api/jobs?tenant=jobs-tenant-b', headers=_auth_header(steward_a_token))
        assert resp.status_code == 200
        assert resp.get_json()['jobs'] == []

    def test_admin_can_filter_by_tenant_query_param(self, client, admin_token):
        jobs.create_job('validate', {'data': {}}, tenant='jobs-tenant-b', username='someone')
        resp = client.get('/api/jobs?tenant=jobs-tenant-b', headers=_auth_header(admin_token))
        assert resp.status_code == 200
        body = resp.get_json()
        assert body['total'] == 1
        assert body['jobs'][0]['tenant'] == 'jobs-tenant-b'

    def test_admin_without_tenant_param_defaults_to_own_tenant(self, client, admin_token):
        jobs.create_job('validate', {'data': {}}, tenant='default', username='admin')
        jobs.create_job('validate', {'data': {}}, tenant='jobs-tenant-b', username='someone')
        resp = client.get('/api/jobs', headers=_auth_header(admin_token))
        assert resp.status_code == 200
        tenants = {j['tenant'] for j in resp.get_json()['jobs']}
        assert tenants == {'default'}

    def test_status_filter(self, client, admin_token):
        pending_id = jobs.create_job('validate', {'data': {}}, tenant='default', username='admin')
        running_id = jobs.create_job('validate', {'data': {}}, tenant='default', username='admin')
        jobs._update_job(running_id, status='running', started_at='2026-01-01T00:00:00+00:00')

        resp = client.get('/api/jobs?status=running', headers=_auth_header(admin_token))
        assert resp.status_code == 200
        body = resp.get_json()
        assert body['total'] == 1
        assert body['jobs'][0]['id'] == running_id
        assert body['jobs'][0]['status'] == 'running'

    def test_limit_param_restricts_result_count(self, client, admin_token):
        for _ in range(5):
            jobs.create_job('validate', {'data': {}}, tenant='default', username='admin')
        resp = client.get('/api/jobs?limit=2', headers=_auth_header(admin_token))
        assert resp.status_code == 200
        body = resp.get_json()
        assert body['total'] == 2
        assert len(body['jobs']) == 2

    def test_offset_param_skips_newest(self, client, admin_token):
        first_id = jobs.create_job('validate', {'data': {}}, tenant='default', username='admin')
        time.sleep(0.01)
        second_id = jobs.create_job('validate', {'data': {}}, tenant='default', username='admin')

        resp = client.get('/api/jobs?offset=1', headers=_auth_header(admin_token))
        assert resp.status_code == 200
        ids = [j['id'] for j in resp.get_json()['jobs']]
        # Ordered by created_at DESC -- offset=1 skips the most recently
        # created job (second_id), leaving the first.
        assert second_id not in ids
        assert first_id in ids

    def test_empty_list_when_no_jobs(self, client, admin_token):
        resp = client.get('/api/jobs', headers=_auth_header(admin_token))
        assert resp.status_code == 200
        body = resp.get_json()
        assert body == {'total': 0, 'jobs': []}


# ---------------------------------------------------------------------------
# GET /api/jobs/<id> -- get_job_endpoint (login_required only; unaffected by
# the role_required bug)
# ---------------------------------------------------------------------------

class TestGetJob:
    def test_no_token_unauthorized(self, client):
        job_id = jobs.create_job('validate', {'data': {}}, tenant='jobs-tenant-a', username='jobs-steward-a')
        resp = client.get(f'/api/jobs/{job_id}')
        assert resp.status_code == 401

    def test_happy_path_owner_can_view(self, client, steward_a_token):
        job_id = jobs.create_job('validate', {'data': {'x': 1}}, tenant='jobs-tenant-a', username='jobs-steward-a')
        resp = client.get(f'/api/jobs/{job_id}', headers=_auth_header(steward_a_token))
        assert resp.status_code == 200
        body = resp.get_json()
        assert body['id'] == job_id
        assert body['job_type'] == 'validate'
        assert body['status'] == 'pending'
        assert body['payload'] == {'data': {'x': 1}}

    def test_not_found_returns_404(self, client, steward_a_token):
        resp = client.get('/api/jobs/does-not-exist', headers=_auth_header(steward_a_token))
        assert resp.status_code == 404
        assert 'not found' in resp.get_json()['error'].lower()

    def test_cross_tenant_non_admin_forbidden(self, client, steward_a_token):
        other_id = jobs.create_job('validate', {'data': {}}, tenant='jobs-tenant-b', username='jobs-steward-b')
        resp = client.get(f'/api/jobs/{other_id}', headers=_auth_header(steward_a_token))
        assert resp.status_code == 403
        assert resp.get_json()['error'] == 'Forbidden'

    def test_admin_can_view_any_tenant(self, client, admin_token):
        other_id = jobs.create_job('validate', {'data': {}}, tenant='jobs-tenant-b', username='jobs-steward-b')
        resp = client.get(f'/api/jobs/{other_id}', headers=_auth_header(admin_token))
        assert resp.status_code == 200
        assert resp.get_json()['id'] == other_id

    def test_readonly_role_can_view_own_tenant(self, client, readonly_a_token):
        """get_job_endpoint only requires login_required, not a specific
        role -- a read-only user in the same tenant can view (correctly,
        since this endpoint isn't role-gated at all)."""
        job_id = jobs.create_job('validate', {'data': {}}, tenant='jobs-tenant-a', username='jobs-steward-a')
        resp = client.get(f'/api/jobs/{job_id}', headers=_auth_header(readonly_a_token))
        assert resp.status_code == 200

    def test_completed_job_includes_result(self, client, admin_token):
        job_id = jobs.create_job('validate', {'data': {}}, tenant='default', username='admin')
        jobs._update_job(job_id, status='completed', result=json.dumps({'is_valid': True}))
        resp = client.get(f'/api/jobs/{job_id}', headers=_auth_header(admin_token))
        assert resp.status_code == 200
        body = resp.get_json()
        assert body['status'] == 'completed'
        assert body['result'] == {'is_valid': True}

    def test_failed_job_includes_error(self, client, admin_token):
        job_id = jobs.create_job('validate', {'data': {}}, tenant='default', username='admin')
        jobs._update_job(job_id, status='failed', error='ValueError: boom')
        resp = client.get(f'/api/jobs/{job_id}', headers=_auth_header(admin_token))
        assert resp.status_code == 200
        body = resp.get_json()
        assert body['status'] == 'failed'
        assert body['error'] == 'ValueError: boom'
