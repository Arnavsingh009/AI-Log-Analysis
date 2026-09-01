from fastapi.testclient import TestClient
from app.main import app

client = TestClient(app)

def test_health_check():
    response = client.get("/")
    assert response.status_code == 200
    assert response.json()["status"] == "healthy"

def test_log_ingestion_info():
    payload = {
        "service_name": "test-service",
        "level": "INFO",
        "message": "User login successful"
    }
    response = client.post("/api/v1/logs", json=payload)
    assert response.status_code == 200
    assert response.json()["status"] == "received"
    assert response.json()["service"] == "test-service"

def test_log_ingestion_error():
    payload = {
        "service_name": "payment-service",
        "level": "ERROR",
        "message": "Gateway timeout",
        "stack_trace": "TimeoutError: Stripe API unreachable at line 55"
    }
    response = client.post("/api/v1/logs", json=payload)
    assert response.status_code == 200
    assert response.json()["incident_id"] is not None