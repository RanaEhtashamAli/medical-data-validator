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


def test_docs_route_exists(client):
    """Test that the /docs route exists and returns documentation."""
    resp = client.get("/docs")
    # Handle redirect (308) by following it
    if resp.status_code == 308:
        resp = client.get("/docs/")
    assert resp.status_code == 200
    # Check for any documentation-related content instead of specific text
    assert b"Documentation" in resp.data or b"documentation" in resp.data or b"API" in resp.data


def test_docs_index_route(client):
    """Test the main documentation index route."""
    resp = client.get("/docs/")
    assert resp.status_code == 200
    assert b"Documentation" in resp.data


def test_docs_api_route(client):
    """Test the API documentation route."""
    resp = client.get("/docs/api")
    assert resp.status_code == 200
    assert b"API Reference" in resp.data


def test_markdown_documentation_route(client):
    """Test serving markdown documentation files."""
    # Test API documentation
    resp = client.get("/docs/markdown/API_DOCUMENTATION.md")
    assert resp.status_code == 200
    assert b"Medical Data Validator API" in resp.data


def test_swagger_ui_route(client):
    """Test that Swagger UI is accessible."""
    resp = client.get("/docs/swagger")
    assert resp.status_code == 200
    assert b"Swagger" in resp.data or b"swagger" in resp.data


def test_swagger_json_route(client):
    """Test that Swagger JSON specification is accessible."""
    resp = client.get("/docs/swagger.json")
    assert resp.status_code == 200

def test_openapi_not_found(client):
    resp = client.get("/api/openapi.json")
    assert resp.status_code in [404, 501]  # Flask does not provide OpenAPI by default 