import pytest
from flask import Flask
from medical_data_validator.dashboard.app import create_dashboard_app

@pytest.fixture(scope="module")
def client():
    app = create_dashboard_app()
    app.config['TESTING'] = True
    with app.test_client() as client:
        yield client

def test_api_root(client):
    resp = client.get("/api/")
    assert resp.status_code == 200
    data = resp.get_json()
    assert data["message"] == "Medical Data Validator API"
    assert data["version"] == "0.1.0"
    assert "developer" in data

def test_api_health(client):
    resp = client.get("/api/health")
    assert resp.status_code == 200
    data = resp.get_json()
    assert data["status"] == "healthy"
    assert data["version"] == "0.1.0"
    assert "timestamp" in data
    assert "standards_supported" in data
    assert isinstance(data["standards_supported"], list)
    assert "icd10" in data["standards_supported"]

def test_api_profiles(client):
    resp = client.get("/api/profiles")
    assert resp.status_code == 200
    data = resp.get_json()
    assert isinstance(data, dict)
    assert "clinical_trials" in data
    assert "ehr" in data
    assert "imaging" in data
    assert "lab" in data

def test_api_standards(client):
    resp = client.get("/api/standards")
    assert resp.status_code == 200
    data = resp.get_json()
    assert isinstance(data, dict)
    assert "icd10" in data
    assert "loinc" in data
    assert "cpt" in data 