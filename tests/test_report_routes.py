"""Tests for the /api/report/* REST API (reports.register_report_routes).

Covers:
  - inline endpoints: POST /api/report/inline/pdf, POST /api/report/inline/csv
  - job-based endpoints: GET /api/report/<id>/pdf, GET /api/report/<id>/csv

Job-based tests seed a completed job directly via jobs.create_job() +
jobs._update_job(status='completed', ...) rather than jobs.submit_job(),
per the plan's global constraint to avoid the documented race condition
between the background worker thread and test-fixture DB teardown.
"""

import os
import tempfile

import pytest

import medical_data_validator.auth as auth
import medical_data_validator.jobs as jobs
from medical_data_validator.dashboard.app import create_dashboard_app
from tests.test_reports import SAMPLE_RESULT, EMPTY_RESULT


@pytest.fixture(scope="module")
def client():
    app = create_dashboard_app()
    app.config['TESTING'] = True
    with app.test_client() as client:
        yield client


@pytest.fixture(autouse=True)
def _isolated_jobs_db():
    """Give each test its own fresh SQLite jobs DB (same pattern as test_jobs.py)."""
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


def _admin_token(client):
    resp = client.post('/api/auth/token', json={
        'username': 'admin',
        'password': os.environ.get('ADMIN_PASSWORD', 'change-me'),
    })
    assert resp.status_code == 200
    return resp.get_json()['access_token']


def _auth_headers(client):
    return {'Authorization': f'Bearer {_admin_token(client)}'}


def _seed_completed_job(result=SAMPLE_RESULT, tenant='default', username='admin'):
    """Create a job and mark it completed with the given result, bypassing
    submit_job()'s background-worker path entirely."""
    import json
    job_id = jobs.create_job('validate', {'data': {}}, tenant=tenant, username=username)
    jobs._update_job(job_id, status='completed', result=json.dumps(result))
    return job_id


# ── Inline endpoints ─────────────────────────────────────────────────────────

class TestInlinePDF:
    def test_returns_real_pdf(self, client):
        resp = client.post(
            '/api/report/inline/pdf', json=SAMPLE_RESULT, headers=_auth_headers(client)
        )
        assert resp.status_code == 200
        assert resp.data[:4] == b'%PDF'
        assert resp.mimetype == 'application/pdf'

    def test_content_disposition_header(self, client):
        resp = client.post(
            '/api/report/inline/pdf', json=SAMPLE_RESULT, headers=_auth_headers(client)
        )
        assert 'attachment; filename="report.pdf"' in resp.headers['Content-Disposition']

    def test_empty_result_still_generates_pdf(self, client):
        resp = client.post(
            '/api/report/inline/pdf', json=EMPTY_RESULT, headers=_auth_headers(client)
        )
        assert resp.status_code == 200
        assert resp.data[:4] == b'%PDF'

    def test_no_body_returns_400(self, client):
        resp = client.post(
            '/api/report/inline/pdf', headers=_auth_headers(client)
        )
        assert resp.status_code == 400
        assert 'error' in resp.get_json()

    def test_empty_json_object_returns_400(self, client):
        # {} is falsy-ish per the route's `if not result` check
        resp = client.post(
            '/api/report/inline/pdf', json={}, headers=_auth_headers(client)
        )
        assert resp.status_code == 400

    def test_requires_authentication(self, client):
        resp = client.post('/api/report/inline/pdf', json=SAMPLE_RESULT)
        assert resp.status_code == 401

    def test_compliance_table_rendered(self, client):
        # SAMPLE_RESULT carries a compliance_report; this exercises the
        # PDF's compliance-table rendering path.
        resp = client.post(
            '/api/report/inline/pdf', json=SAMPLE_RESULT, headers=_auth_headers(client)
        )
        assert resp.status_code == 200
        assert resp.data[:4] == b'%PDF'
        assert len(resp.data) > 1024

    def test_compliance_table_skip_keys_branch(self, client):
        # generate_pdf_report()'s compliance-table loop does
        # `standards = compliance.get('standards', compliance)` — when the
        # compliance_report has no 'standards' wrapper (a flattened/legacy
        # shape), it falls back to iterating the compliance dict itself,
        # which mixes real per-standard entries with non-standard keys
        # ('all_violations', 'overall_score', 'risk_level',
        # 'template_applied') that must be skipped. This exercises that
        # skip-keys continue branch.
        result = dict(SAMPLE_RESULT)
        result['summary'] = dict(SAMPLE_RESULT['summary'])
        result['summary']['compliance_report'] = {
            'hipaa': {'score': 80.0, 'risk_level': 'low', 'compliant': True},
            'all_violations': [],
            'overall_score': 80.0,
            'risk_level': 'low',
            'template_applied': None,
        }
        resp = client.post(
            '/api/report/inline/pdf', json=result, headers=_auth_headers(client)
        )
        assert resp.status_code == 200
        assert resp.data[:4] == b'%PDF'


class TestInlineCSV:
    def test_returns_real_csv(self, client):
        resp = client.post(
            '/api/report/inline/csv', json=SAMPLE_RESULT, headers=_auth_headers(client)
        )
        assert resp.status_code == 200
        assert resp.mimetype == 'text/csv'
        text = resp.data.decode('utf-8')
        assert 'severity' in text
        assert 'SchemaValidator' in text
        assert 'Value out of range' in text

    def test_content_disposition_header(self, client):
        resp = client.post(
            '/api/report/inline/csv', json=SAMPLE_RESULT, headers=_auth_headers(client)
        )
        assert 'attachment; filename="report.csv"' in resp.headers['Content-Disposition']

    def test_empty_result_says_valid(self, client):
        resp = client.post(
            '/api/report/inline/csv', json=EMPTY_RESULT, headers=_auth_headers(client)
        )
        assert resp.status_code == 200
        assert 'VALID' in resp.data.decode('utf-8')

    def test_no_body_returns_400(self, client):
        resp = client.post(
            '/api/report/inline/csv', headers=_auth_headers(client)
        )
        assert resp.status_code == 400

    def test_requires_authentication(self, client):
        resp = client.post('/api/report/inline/csv', json=SAMPLE_RESULT)
        assert resp.status_code == 401


# ── Job-based endpoints ──────────────────────────────────────────────────────

class TestJobPDF:
    def test_returns_real_pdf_for_completed_job(self, client):
        job_id = _seed_completed_job()
        resp = client.get(f'/api/report/{job_id}/pdf', headers=_auth_headers(client))
        assert resp.status_code == 200
        assert resp.data[:4] == b'%PDF'
        assert resp.mimetype == 'application/pdf'

    def test_content_disposition_includes_job_id(self, client):
        job_id = _seed_completed_job()
        resp = client.get(f'/api/report/{job_id}/pdf', headers=_auth_headers(client))
        assert f'report-{job_id}.pdf' in resp.headers['Content-Disposition']

    def test_unknown_job_returns_404(self, client):
        resp = client.get('/api/report/no-such-job/pdf', headers=_auth_headers(client))
        assert resp.status_code == 404
        assert 'error' in resp.get_json()

    def test_pending_job_returns_409(self, client):
        job_id = jobs.create_job('validate', {'data': {}}, tenant='default', username='admin')
        resp = client.get(f'/api/report/{job_id}/pdf', headers=_auth_headers(client))
        assert resp.status_code == 409
        assert 'pending' in resp.get_json()['error']

    def test_failed_job_returns_409(self, client):
        job_id = jobs.create_job('validate', {'data': {}}, tenant='default', username='admin')
        jobs._update_job(job_id, status='failed', error='boom')
        resp = client.get(f'/api/report/{job_id}/pdf', headers=_auth_headers(client))
        assert resp.status_code == 409
        assert 'failed' in resp.get_json()['error']

    def test_cross_tenant_job_forbidden_for_non_admin(self, client):
        # Seed a job under a different tenant, then access it as a
        # non-admin user scoped to 'default' -> should be 403.
        job_id = _seed_completed_job(tenant='other-tenant', username='someone')

        auth.create_user_account('steward-reports', 'password123', role='data-steward', tenant='default')
        try:
            resp = client.post('/api/auth/token', json={
                'username': 'steward-reports', 'password': 'password123',
            })
            token = resp.get_json()['access_token']
            resp = client.get(
                f'/api/report/{job_id}/pdf',
                headers={'Authorization': f'Bearer {token}'},
            )
            assert resp.status_code == 403
        finally:
            auth.deactivate_user_account('steward-reports')

    def test_admin_can_access_other_tenants_job(self, client):
        job_id = _seed_completed_job(tenant='other-tenant', username='someone')
        resp = client.get(f'/api/report/{job_id}/pdf', headers=_auth_headers(client))
        assert resp.status_code == 200
        assert resp.data[:4] == b'%PDF'

    def test_requires_authentication(self, client):
        job_id = _seed_completed_job()
        resp = client.get(f'/api/report/{job_id}/pdf')
        assert resp.status_code == 401

    def test_non_dict_result_returns_500(self, client):
        import json
        job_id = jobs.create_job('validate', {'data': {}}, tenant='default', username='admin')
        jobs._update_job(job_id, status='completed', result=json.dumps(['not', 'a', 'dict']))
        resp = client.get(f'/api/report/{job_id}/pdf', headers=_auth_headers(client))
        assert resp.status_code == 500


class TestJobCSV:
    def test_returns_real_csv_for_completed_job(self, client):
        job_id = _seed_completed_job()
        resp = client.get(f'/api/report/{job_id}/csv', headers=_auth_headers(client))
        assert resp.status_code == 200
        assert resp.mimetype == 'text/csv'
        text = resp.data.decode('utf-8')
        assert 'PHIDetector' in text
        assert 'Potential PHI detected' in text

    def test_content_disposition_includes_job_id(self, client):
        job_id = _seed_completed_job()
        resp = client.get(f'/api/report/{job_id}/csv', headers=_auth_headers(client))
        assert f'report-{job_id}.csv' in resp.headers['Content-Disposition']

    def test_unknown_job_returns_404(self, client):
        resp = client.get('/api/report/no-such-job/csv', headers=_auth_headers(client))
        assert resp.status_code == 404

    def test_pending_job_returns_409(self, client):
        job_id = jobs.create_job('validate', {'data': {}}, tenant='default', username='admin')
        resp = client.get(f'/api/report/{job_id}/csv', headers=_auth_headers(client))
        assert resp.status_code == 409

    def test_requires_authentication(self, client):
        job_id = _seed_completed_job()
        resp = client.get(f'/api/report/{job_id}/csv')
        assert resp.status_code == 401
