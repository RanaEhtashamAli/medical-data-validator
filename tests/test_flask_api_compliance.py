import pytest
from flask import Flask
from medical_data_validator.dashboard.app import create_dashboard_app

@pytest.fixture(scope="module")
def client():
    app = create_dashboard_app()
    app.config['TESTING'] = True
    with app.test_client() as client:
        yield client

def test_compliance_check_basic(client):
    test_data = {
        "patient_id": ["001", "002"],
        "age": [30, 45],
        "diagnosis": ["E11.9", "I10"]
    }
    resp = client.post("/api/compliance/check", json=test_data)
    assert resp.status_code == 200
    data = resp.get_json()
    assert "hipaa_compliant" in data
    assert "icd10_compliant" in data
    assert "details" in data

def test_compliance_check_with_phi(client):
    test_data = {
        "patient_id": ["001", "002"],
        "ssn": ["123-45-6789", "987-65-4321"],
        "email": ["test@example.com", "user@example.com"]
    }
    resp = client.post("/api/compliance/check", json=test_data)
    assert resp.status_code == 200
    data = resp.get_json()
    assert "hipaa_compliant" in data
    assert data["hipaa_compliant"] is False

def test_compliance_check_all_standards(client):
    test_data = {
        "patient_id": ["001", "002"],
        "icd10_code": ["E11.9", "I10"],
        "loinc_code": ["58410-2", "789-8"],
        "cpt_code": ["99213", "93010"]
    }
    resp = client.post("/api/compliance/check", json=test_data)
    assert resp.status_code == 200
    data = resp.get_json()
    assert "hipaa_compliant" in data
    assert "icd10_compliant" in data
    assert "loinc_compliant" in data
    assert "cpt_compliant" in data
    assert "details" in data 