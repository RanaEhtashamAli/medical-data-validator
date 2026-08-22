"""Tests for API route registration: de-duplication and v1.2 wiring."""

import pytest
from medical_data_validator.dashboard.app import create_dashboard_app


@pytest.fixture(scope="module")
def client():
    app = create_dashboard_app()
    app.config['TESTING'] = True
    with app.test_client() as client:
        yield client


def test_no_duplicate_route_registration_for_the_six_shared_paths(client):
    """The 6 paths flask-restx now owns exclusively must resolve exactly once
    at the URL-map level, not twice (blueprint + restx)."""
    app = create_dashboard_app()
    rules_by_path = {}
    for rule in app.url_map.iter_rules():
        rules_by_path.setdefault(rule.rule, []).append(rule.endpoint)
    for path in ('/api/health', '/api/validate/data', '/api/validate/file',
                 '/api/compliance/check', '/api/profiles', '/api/standards'):
        assert path in rules_by_path, f"{path} missing entirely"
        assert len(rules_by_path[path]) == 1, f"{path} still registered {len(rules_by_path[path])} times"


def test_blueprint_only_routes_still_present(client):
    """The 13 routes with no restx equivalent must survive the de-dup."""
    r = client.get('/api/monitoring/stats')
    assert r.status_code != 404
    r = client.get('/api/compliance/templates')
    assert r.status_code != 404
    app = create_dashboard_app()
    paths = {rule.rule for rule in app.url_map.iter_rules()}
    assert '/api/' in paths


def test_v1_2_compliance_check_uses_the_v1_2_handler(client):
    """Regression test: /v1.2/compliance/check was silently calling the
    legacy v1.0 handler (api_compliance_check, JSON-body contract) instead
    of the real v1.2 one (api_v1_2_compliance, file-upload contract)."""
    import io
    csv_bytes = b"ssn,notes\n123-45-6789,a\n"
    resp = client.post(
        '/v1.2/compliance/check',
        data={'file': (io.BytesIO(csv_bytes), 'test.csv')},
        content_type='multipart/form-data',
    )
    assert resp.status_code == 200
    body = resp.get_json()
    # api_v1_2_compliance's response shape is {success, message,
    # compliance_report} — the legacy v1.0 handler's shape has neither
    # 'success' nor 'compliance_report' as top-level keys.
    assert 'compliance_report' in body
    assert 'risk_level' in body['compliance_report']
