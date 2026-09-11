import pytest
from fastapi.testclient import TestClient
from backend.app.config.settings import Settings
from backend.app.main import app

def test_cors_settings_parsing():
    # Comma-separated parsing and trailing slash stripping
    s = Settings(CORS_ORIGINS="http://localhost:5173/, http://127.0.0.1:5173,https://app.cybershield.gov.in/")
    assert s.cors_origins_list == [
        "http://localhost:5173",
        "http://127.0.0.1:5173",
        "https://app.cybershield.gov.in"
    ]

def test_cors_settings_local_dev_defaults():
    s = Settings(ENVIRONMENT="development", CORS_ORIGINS="http://localhost:5173,http://127.0.0.1:5173")
    assert "http://localhost:5173" in s.cors_origins_list
    assert "http://127.0.0.1:5173" in s.cors_origins_list

def test_cors_production_rejects_wildcard():
    # Production must NOT allow wildcard CORS with credentials
    with pytest.raises(ValueError, match="Production configuration error: CORS_ORIGINS"):
        Settings(
            ENVIRONMENT="production",
            JWT_SECRET="valid-production-secret-key-1234567890",
            CORS_ORIGINS="*"
        )

def test_cors_production_rejects_empty():
    with pytest.raises(ValueError, match="Production configuration error: CORS_ORIGINS"):
        Settings(
            ENVIRONMENT="production",
            JWT_SECRET="valid-production-secret-key-1234567890",
            CORS_ORIGINS=""
        )

def test_cors_allowed_origin_response():
    client = TestClient(app)
    # Preflight OPTIONS request from allowed origin
    headers = {
        "Origin": "http://localhost:5173",
        "Access-Control-Request-Method": "GET",
    }
    response = client.options("/health", headers=headers)
    assert response.status_code == 200
    assert response.headers.get("access-control-allow-origin") == "http://localhost:5173"
    assert response.headers.get("access-control-allow-credentials") == "true"

def test_cors_disallowed_origin_rejected():
    client = TestClient(app)
    headers = {
        "Origin": "http://unauthorized-domain.com",
        "Access-Control-Request-Method": "GET",
    }
    response = client.options("/health", headers=headers)
    # Disallowed origin should not have access-control-allow-origin
    assert response.headers.get("access-control-allow-origin") is None
