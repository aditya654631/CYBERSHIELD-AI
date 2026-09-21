from fastapi.testclient import TestClient
from backend.app.main import app
from backend.app.auth.security import create_access_token
from backend.app.models.models import User, Organization

client = TestClient(app)


def test_system_status_requires_auth():
    # Without token -> 401 Unauthorized
    response = client.get("/api/v1/system/status")
    assert response.status_code == 401


def test_system_status_authenticated_returns_truthful_telemetry(db_session):
    # Setup test user
    org = Organization(name="Test I4C HQ", org_type="I4C", state="National", district="ALL")
    db_session.add(org)
    db_session.commit()

    user = User(
        email="operator.test@cybershield.gov.in",
        hashed_password="fakehashedpassword",
        full_name="Test Operator",
        role="I4C_ADMIN",
        organization_id=org.id,
        is_active=True
    )
    db_session.add(user)
    db_session.commit()

    token = create_access_token(data={"sub": user.email, "role": user.role})
    headers = {"Authorization": f"Bearer {token}"}

    response = client.get("/api/v1/system/status", headers=headers)
    assert response.status_code == 200
    data = response.json()

    # Invariants
    assert "environment" in data
    assert "database" in data
    assert "ml_engine" in data
    assert "websocket" in data
    assert "integrations" in data
    assert isinstance(data["database"]["latency_ms"], (int, float))
    assert data["database"]["latency_ms"] >= 0
    assert data["timestamp"]

    # Truthful simulation reporting
    assert data["integrations"]["bank_gateway"]["is_simulated"] is True
    assert data["integrations"]["bank_gateway"]["status"] == "SIMULATED_LOCAL"
    assert data["integrations"]["blockchain_gateway"]["is_simulated"] is True

    # ML engine artifact verification presence
    assert "artifact_verification" in data["ml_engine"]
    assert "model_version" in data["ml_engine"]
