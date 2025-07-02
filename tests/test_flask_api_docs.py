import pytest
from flask import Flask
from medical_data_validator.dashboard.app import create_dashboard_app

@pytest.fixture(scope="module")
def client():
    app = create_dashboard_app()
    app.config['TESTING'] = True
    with app.test_client() as client:
        yield client

def test_docs_not_found(client):
    resp = client.get("/api/docs")
    assert resp.status_code in [404, 501]  # Flask does not provide Swagger by default

def test_openapi_not_found(client):
    resp = client.get("/api/openapi.json")
    assert resp.status_code in [404, 501]  # Flask does not provide OpenAPI by default 