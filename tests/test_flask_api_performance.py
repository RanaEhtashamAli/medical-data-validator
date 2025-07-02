import pytest
import threading
import time
from flask import Flask
from medical_data_validator.dashboard.app import create_dashboard_app

@pytest.fixture(scope="module")
def client():
    app = create_dashboard_app()
    app.config['TESTING'] = True
    with app.test_client() as client:
        yield client

def test_large_dataset_validation(client):
    large_data = {
        "patient_id": [f"P{i:06d}" for i in range(1000)],
        "age": [30 + (i % 50) for i in range(1000)],
        "diagnosis": ["E11.9" if i % 2 == 0 else "I10" for i in range(1000)]
    }
    resp = client.post("/api/validate/data", json=large_data)
    assert resp.status_code == 200
    data = resp.get_json()
    assert data["success"] is True
    assert "summary" in data
    assert data["summary"]["total_rows"] == 1000

def test_concurrent_requests():
    results = []
    def make_request():
        app = create_dashboard_app()
        app.config['TESTING'] = True
        with app.test_client() as client:
            test_data = {
                "patient_id": ["001", "002"],
                "age": [30, 45],
                "diagnosis": ["E11.9", "I10"]
            }
            resp = client.post("/api/validate/data", json=test_data)
            results.append(resp.status_code)
    
    threads = []
    for _ in range(5):
        t = threading.Thread(target=make_request)
        threads.append(t)
        t.start()
    for t in threads:
        t.join()
    assert all(status == 200 for status in results)

def test_response_time(client):
    test_data = {
        "patient_id": ["001", "002"],
        "age": [30, 45],
        "diagnosis": ["E11.9", "I10"]
    }
    start = time.time()
    resp = client.post("/api/validate/data", json=test_data)
    end = time.time()
    assert resp.status_code == 200
    assert (end - start) < 5.0 