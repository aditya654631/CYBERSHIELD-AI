"""
Verification script for Sections 11 (WebSocket Single-Use Ticket) and 12 (Health / Model Identity)
"""

import os
import sys
import json
import pytest
from starlette.testclient import TestClient

sys.path.insert(0, os.path.abspath("."))

from backend.app.main import app
from backend.app.config.settings import settings
from backend.app.models.db import SessionLocal
from backend.app.models.models import User, Organization
from backend.app.auth.security import create_access_token, verify_ws_token

def test_websocket_ticket_single_use():
    print("\n" + "="*70)
    print("11. WEBSOCKET SINGLE-USE TICKET AUDIT")
    print("="*70)
    
    db = SessionLocal()
    try:
        user = db.query(User).filter(User.is_active == True).first()
        if not user:
            print("No active user found in DB to test WS ticket")
            return
            
        client = TestClient(app)
        auth_token = create_access_token(data={"sub": user.email, "role": user.role})
        
        # 1. Issue ticket
        res = client.post("/api/v1/auth/ws/ticket", headers={"Authorization": f"Bearer {auth_token}"})
        print(f"Issue Ticket Status Code: {res.status_code}")
        assert res.status_code == 200, f"Expected 200, got {res.status_code}"
        ticket_data = res.json()
        ticket = ticket_data["ticket"]
        jti = ticket_data.get("jti")
        print(f"Issued Ticket JTI: {jti}, expires_in: {ticket_data.get('expires_in')}s")
        
        # 2. First verification (should SUCCEED)
        user_verified = verify_ws_token(ticket, db)
        print(f"First verification: SUCCESS (User: {user_verified.email})")
        
        # 3. Second verification with same ticket (should be REJECTED)
        rejected = False
        try:
            verify_ws_token(ticket, db)
        except Exception as e:
            rejected = True
            print(f"Second verification (Re-use attempt): REJECTED as expected ({e.detail if hasattr(e, 'detail') else e})")
            
        assert rejected, "Security Violation: Same WebSocket ticket was reused successfully!"
        print("TICKET SINGLE-USE VERIFICATION: PASSED (Strictly consumed on first use)")
    finally:
        db.close()

def test_health_endpoints_and_model_identity():
    print("\n" + "="*70)
    print("12. HEALTH / MODEL IDENTITY AUDIT")
    print("="*70)
    
    client = TestClient(app)
    
    # 1. GET /health/live
    live_res = client.get("/health/live")
    print(f"GET /health/live -> Status: {live_res.status_code}, Body: {live_res.json()}")
    assert live_res.status_code == 200
    
    # 2. GET /health/ready
    ready_res = client.get("/health/ready")
    print(f"GET /health/ready -> Status: {ready_res.status_code}, Body: {ready_res.json()}")
    assert ready_res.status_code in (200, 503)
    
    # 3. Model identity test in prediction response
    from backend.app.services.prediction_service import PredictionService, EXPECTED_HASHES, ACTIVE_LOCATION_MODEL_VERSION
    ps = PredictionService()
    active_v = getattr(ps.ml_provider, 'model_version', ACTIVE_LOCATION_MODEL_VERSION)
    print(f"Prediction Service Reported Active Version: {active_v}")
    
    db = SessionLocal()
    try:
        from backend.app.models.models import Complaint
        comp = db.query(Complaint).first()
        if comp:
            res_pred = ps.run_prediction(db, comp.id)
            print(f"Complaint Prediction Run Model Reported: {res_pred.get('model_version')} (status: {res_pred.get('status')})")
            assert res_pred.get("model_version") is not None, "Model identity missing in prediction response"
    finally:
        db.close()

    # 4. Simulate model verification failure
    print("\n--- Simulating Active Model Degradation ---")
    from backend.app.services.model_verification_service import model_verification_service
    orig_verify = model_verification_service.verify_model_artifacts
    try:
        model_verification_service.verify_model_artifacts = lambda f: {"is_ready": False, "status": "TAMPERED_CHECKSUM"}
        ready_fail_res = client.get("/health/ready")
        print(f"Simulated Degradation GET /health/ready -> Status: {ready_fail_res.status_code}, Body: {ready_fail_res.json()}")
        assert ready_fail_res.status_code == 503, f"Expected 503 on degraded model, got {ready_fail_res.status_code}"
        live_res2 = client.get("/health/live")
        print(f"Simulated Degradation GET /health/live -> Status: {live_res2.status_code} (Remains 200 alive)")
        assert live_res2.status_code == 200
        print("HEALTH READINESS FAILURE SIMULATION: PASSED (503 on degraded model, 200 on live)")
    finally:
        model_verification_service.verify_model_artifacts = orig_verify

if __name__ == "__main__":
    test_websocket_ticket_single_use()
    test_health_endpoints_and_model_identity()
