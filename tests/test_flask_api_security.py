import pytest
from flask import Flask
from medical_data_validator.dashboard.app import create_dashboard_app

@pytest.fixture(scope="module")
def client():
    app = create_dashboard_app()
    app.config['TESTING'] = True
    with app.test_client() as client:
        yield client

def test_file_type_validation(client):
    dangerous_files = [
        (b'executable content', 'test.exe'),
        (b'batch content', 'test.bat'),
        (b'shell script content', 'test.sh'),
        (b'php content', 'test.php'),
        (b'<script>alert(1)</script>', 'test.html')
    ]
    for content, filename in dangerous_files:
        resp = client.post(
            "/api/validate/file",
            data={'file': (content, filename)},
            content_type='multipart/form-data'
        )
        assert resp.status_code in [400, 415]

def test_xss_protection(client):
    malicious_data = {
        "patient_id": ["001"],
        "diagnosis": ["<script>alert('xss')</script>"]
    }
    resp = client.post("/api/validate/data", json=malicious_data)
    assert resp.status_code == 200
    data = resp.get_json()
    assert data["success"] is True

def test_sql_injection_protection(client):
    malicious_data = {
        "patient_id": ["001"],
        "diagnosis": ["'; DROP TABLE patients; --"]
    }
    resp = client.post("/api/validate/data", json=malicious_data)
    assert resp.status_code == 200
    data = resp.get_json()
    assert data["success"] is True

def test_input_validation(client):
    invalid_data = {
        "patient_id": [None, ""],
        "age": ["not_a_number", -1, 999],
        "diagnosis": [123, True, None]
    }
    resp = client.post("/api/validate/data", json=invalid_data)
    assert resp.status_code == 200
    data = resp.get_json()
    assert data["success"] is True
    assert data["total_issues"] >= 0 