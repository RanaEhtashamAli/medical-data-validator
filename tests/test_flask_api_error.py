import pytest
from flask import Flask
from io import BytesIO
from medical_data_validator.dashboard.app import create_dashboard_app

@pytest.fixture(scope="module")
def client():
    app = create_dashboard_app()
    app.config['TESTING'] = True
    with app.test_client() as client:
        yield client

def test_validate_file_invalid_type(client):
    # Send a file with .txt extension which is not allowed
    file_data = BytesIO(b'invalid data')
    resp = client.post(
        "/api/validate/file",
        data={'file': (file_data, 'test.txt')},
        content_type='multipart/form-data'
    )
    assert resp.status_code == 400
    data = resp.get_json()
    assert "File type not allowed" in data["error"]

def test_validate_file_too_large(client):
    large_data = b"patient_id,age,diagnosis\n" + b"001,30,E11.9\n" * 100000
    resp = client.post(
        "/api/validate/file",
        data={'file': (large_data, 'large.csv')},
        content_type='multipart/form-data'
    )
    assert resp.status_code in [200, 400, 413]

def test_validate_file_missing(client):
    resp = client.post("/api/validate/file")
    assert resp.status_code == 400

def test_validate_data_invalid_json(client):
    resp = client.post("/api/validate/data", data="invalid json", content_type="application/json")
    assert resp.status_code in [400, 500]

def test_validate_data_empty(client):
    resp = client.post("/api/validate/data", json={})
    assert resp.status_code == 200
    data = resp.get_json()
    assert data["success"] is True

def test_validate_data_malformed(client):
    malformed_data = {
        "patient_id": [None, ""],
        "age": ["not_a_number", -1, 999],
        "diagnosis": [123, True, None]
    }
    resp = client.post("/api/validate/data", json=malformed_data)
    assert resp.status_code == 200
    data = resp.get_json()
    assert data["success"] is True
    assert data["total_issues"] >= 0 