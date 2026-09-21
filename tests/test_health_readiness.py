"""
Unit and Integration Tests for Liveness and Readiness Probes
Master Corrective Pass V3
"""

import pytest
from fastapi.testclient import TestClient
import os
import sys

BASE_DIR = os.path.abspath(os.path.join(os.path.dirname(__file__), ".."))
if BASE_DIR not in sys.path:
    sys.path.insert(0, BASE_DIR)

from backend.app.main import app

client = TestClient(app)


def test_health_live_endpoint():
    """Verify /health/live returns HTTP 200 with alive status."""
    res = client.get("/health/live")
    assert res.status_code == 200
    data = res.json()
    assert data.get("status") == "alive"
    assert "timestamp" in data


def test_health_ready_endpoint():
    """Verify /health/ready returns status code 200 or 503 depending on database/model readiness."""
    res = client.get("/health/ready")
    assert res.status_code in (200, 503)
    data = res.json()
    assert "status" in data
    assert "database_connected" in data
    assert "model_available" in data
    assert "model_verified" in data
