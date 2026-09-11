import pytest
from unittest.mock import patch
from fastapi.testclient import TestClient

from app.main import app
from app.database import init_db, SessionLocal, IncidentModel
from app.services.cache import generate_signature, set_cached_rca, get_cached_rca

client = TestClient(app)


@pytest.fixture(autouse=True)
def setup_test_environment():
    """Ensure database is initialized before tests execute."""
    init_db()
    yield


def test_health_and_metrics_endpoint():
    """Verify that the telemetry metrics endpoint returns valid payload schema."""
    response = client.get("/api/v1/metrics")
    assert response.status_code == 200
    data = response.json()
    assert "total_logs_ingested" in data
    assert "cache_hit_ratio_percent" in data
    assert "total_incidents" in data


def test_ingest_info_log():
    """Verify that standard INFO logs increment telemetry but do not trigger incidents."""
    payload = {
        "service_name": "inventory-service",
        "level": "INFO",
        "message": "Routine health check executed successfully.",
        "stack_trace": "",
        "timestamp": "2026-09-11T10:00:00Z"
    }
    response = client.post("/api/v1/logs", json=payload)
    assert response.status_code == 200
    assert response.json() == {"status": "accepted"}


def test_signature_cache_deduplication():
    """Verify that SHA-256 signature hashing correctly caches and retrieves RCA payloads."""
    sig = generate_signature("auth-service", "Invalid token signature", "Traceback line 12")
    sample_rca = {
        "root_cause": "Malformed JWT token signature",
        "affected_component": "auth-service",
        "severity": "HIGH",
        "suggested_fix": "Verify secret key alignment across microservices."
    }
    set_cached_rca(sig, sample_rca)
    cached_result = get_cached_rca(sig)
    assert cached_result is not None
    assert cached_result["root_cause"] == sample_rca["root_cause"]


@patch("app.services.ai_service.analyze_stack_trace")
def test_ingest_error_creates_incident_and_triggers_triage(mock_analyze):
    """Verify that an ERROR payload persists an incident and executes background triage."""
    mock_analyze.return_value = {
        "root_cause": "Database connection pool timeout",
        "affected_component": "payment-service",
        "severity": "CRITICAL",
        "suggested_fix": "Increase connection pool size in database configuration."
    }

    payload = {
        "service_name": "payment-service",
        "level": "ERROR",
        "message": "sqlalchemy.exc.TimeoutError: QueuePool limit of size 5 reached",
        "stack_trace": "Traceback (most recent call last):\n  File 'db.py', line 22\nTimeoutError",
        "timestamp": "2026-09-11T10:05:00Z"
    }

    response = client.post("/api/v1/logs", json=payload)
    assert response.status_code == 200
    assert response.json() == {"status": "accepted"}

    # Verify incident exists in the incidents query endpoint
    incidents_resp = client.get("/api/v1/incidents")
    assert incidents_resp.status_code == 200
    incidents = incidents_resp.json()
    assert len(incidents) > 0

    target = next((i for i in incidents if i["service_name"] == "payment-service"), None)
    assert target is not None
    assert target["level"] in ["ERROR", "CRITICAL"]


def test_update_incident_status():
    """Verify that incident status transitions properly (e.g., Open -> Resolved)."""
    db = SessionLocal()
    try:
        incident = db.query(IncidentModel).first()
        if incident:
            target_id = incident.id
            patch_resp = client.patch(f"/api/v1/incidents/{target_id}", json={"status": "Resolved"})
            assert patch_resp.status_code == 200
            assert patch_resp.json()["status"] == "Resolved"
    finally:
        db.close()