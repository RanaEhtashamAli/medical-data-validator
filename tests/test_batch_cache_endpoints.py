"""Tests for opt-in batch_size/use_cache on the validate endpoints (Phase B)."""

import pytest
from medical_data_validator.dashboard.app import create_dashboard_app


@pytest.fixture(scope="module")
def client():
    app = create_dashboard_app()
    app.config['TESTING'] = True
    with app.test_client() as client:
        yield client


def test_validate_data_without_batch_size_is_unchanged(client):
    resp = client.post('/api/validate/data', json={'age': [200]})
    assert resp.status_code == 200
    body = resp.get_json()
    assert 'batch_results' not in body.get('summary', {})


def test_validate_data_with_batch_size_uses_batch_validator(client):
    resp = client.post('/api/validate/data?batch_size=1', json={'age': [1, 2, 3]})
    assert resp.status_code == 200
    body = resp.get_json()
    assert 'batch_results' in body['summary']
    assert body['summary']['total_batches'] == 3


def test_validate_data_batch_with_cache_produces_same_result_twice(client):
    resp1 = client.post('/api/validate/data?batch_size=1&use_cache=true', json={'age': [1]})
    resp2 = client.post('/api/validate/data?batch_size=1&use_cache=true', json={'age': [1]})
    assert resp1.get_json()['total_issues'] == resp2.get_json()['total_issues']
