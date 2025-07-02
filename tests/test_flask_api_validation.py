import pytest
import io
import json
import pandas as pd
from flask import Flask
from medical_data_validator.dashboard.app import create_dashboard_app

@pytest.fixture(scope="module")
def client():
    app = create_dashboard_app()
    app.config['TESTING'] = True
    with app.test_client() as client:
        yield client

def test_validate_data_json(client):
    test_data = {
        "patient_id": ["001", "002"],
        "age": [30, 45],
        "diagnosis": ["E11.9", "I10"]
    }
    resp = client.post("/api/validate/data", json=test_data)
    assert resp.status_code == 200
    data = resp.get_json()
    assert data["success"] is True
    assert "is_valid" in data
    assert "total_issues" in data
    assert "compliance_report" in data
    assert "summary" in data
    assert "issues" in data

def test_validate_data_with_phi(client):
    test_data = {
        "patient_id": ["001", "002"],
        "ssn": ["123-45-6789", "987-65-4321"],
        "email": ["test@example.com", "user@example.com"]
    }
    resp = client.post("/api/validate/data", json=test_data)
    assert resp.status_code == 200
    data = resp.get_json()
    assert data["success"] is True
    assert data["total_issues"] > 0

def test_validate_file_csv(client):
    csv_data = "patient_id,age,diagnosis\n001,30,E11.9\n002,45,I10"
    data = {
        'file': (io.BytesIO(csv_data.encode()), 'test.csv')
    }
    resp = client.post("/api/validate/file", data=data, content_type='multipart/form-data')
    assert resp.status_code == 200
    result = resp.get_json()
    assert result["success"] is True
    assert "is_valid" in result
    assert "total_issues" in result
    assert "summary" in result

def test_validate_file_json(client):
    json_data = {
        "patient_id": ["001", "002"],
        "age": [30, 45],
        "diagnosis": ["E11.9", "I10"]
    }
    data = {
        'file': (io.BytesIO(json.dumps(json_data).encode()), 'test.json')
    }
    resp = client.post("/api/validate/file", data=data, content_type='multipart/form-data')
    assert resp.status_code == 200
    result = resp.get_json()
    assert result["success"] is True
    assert "is_valid" in result