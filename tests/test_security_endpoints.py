"""Tests for the new /api/security/* endpoints (Phase B)."""

import io
import os
import tempfile
import pytest
from medical_data_validator.dashboard.app import create_dashboard_app


@pytest.fixture(scope="module")
def client():
    app = create_dashboard_app()
    app.config['TESTING'] = True
    with app.test_client() as client:
        yield client


def test_hipaa_check_json_body(client):
    resp = client.post('/api/security/hipaa-check', json={'ssn': ['123-45-6789']})
    assert resp.status_code == 200
    body = resp.get_json()
    assert body['compliant'] is False
    assert body['total_phi_instances'] >= 1


def test_hipaa_check_redacts_samples_by_default(client):
    resp = client.post('/api/security/hipaa-check', json={'ssn': ['123-45-6789']})
    body = resp.get_json()
    for item in body['phi_detected']:
        assert 'sample_values' not in item
        assert 'sample_count' in item


def test_hipaa_check_include_samples_opt_in(client):
    resp = client.post('/api/security/hipaa-check?include_samples=true', json={'ssn': ['123-45-6789']})
    body = resp.get_json()
    assert any('sample_values' in item for item in body['phi_detected'])


def test_security_audit_json_body(client):
    resp = client.post('/api/security/audit', json={'email': ['a@b.com']})
    assert resp.status_code == 200
    body = resp.get_json()
    assert 'security_score' in body
    assert body['overall_status'] in ('SECURE', 'NEEDS_ATTENTION')


def test_security_audit_file_upload_gets_real_file_path(client):
    data = {'file': (io.BytesIO(b'ssn\n123-45-6789\n'), 'test.csv')}
    resp = client.post('/api/security/audit', data=data, content_type='multipart/form-data')
    assert resp.status_code == 200
    body = resp.get_json()
    assert body['file_path'] is not None


def test_sanitize_removes_script_tags(client):
    resp = client.post('/api/security/sanitize', json={'notes': ['<script>alert(1)</script>hello']})
    assert resp.status_code == 200
    body = resp.get_json()
    assert body['sanitized_data'][0]['notes'] == 'hello'


def test_security_endpoints_reject_no_input(client):
    resp = client.post('/api/security/hipaa-check', data='', content_type='application/json')
    assert resp.status_code == 400


def test_temp_file_cleaned_up_on_parse_error(client):
    """Regression test: verify temp files are cleaned up when file parsing fails.

    If a file has a valid extension (.csv) but unparseable content (empty),
    load_data() will raise an exception. The endpoint should return 400,
    and the temp file should be cleaned up before the error is returned,
    not leaked for the OS to handle.
    """
    # Capture temp dir state before
    tmp_dir = tempfile.gettempdir()
    before_files = set(os.listdir(tmp_dir))

    # Upload an empty CSV (valid extension, unparseable content)
    data = {'file': (io.BytesIO(b''), 'broken.csv')}
    resp = client.post('/api/security/hipaa-check', data=data, content_type='multipart/form-data')

    # Should return 400 (bad input)
    assert resp.status_code == 400
    body = resp.get_json()
    assert 'error' in body

    # Capture temp dir state after
    after_files = set(os.listdir(tmp_dir))

    # Verify no new temp files were left behind
    new_files = after_files - before_files
    assert len(new_files) == 0, f"Temp files leaked: {new_files}"
