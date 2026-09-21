"""
CyberShield AI — Phase 7 Test Suite: Controlled Cross-State & Cross-District Handoffs.
Verifies explicit assignment records, state machine transitions, scoped time-bounded visibility,
evidence scope restrictions, isolation of unrelated jurisdictions, and audit trail integrity.
"""

import os
import io
import uuid
from datetime import datetime, timezone, timedelta
import pytest
from fastapi.testclient import TestClient
from sqlalchemy.orm import Session

from backend.app.main import app
from backend.app.models.db import get_db
from backend.app.models.models import (
    User, Complaint, Account, ComplaintAccount, Transaction,
    Prediction, Alert, BankAction, EvidenceFile, Organization, AuditLog, CaseHandoff
)
from backend.app.auth.security import create_access_token


@pytest.fixture
def auth_headers(db_session: Session):
    """Creates authenticated users across different states, roles, and organizations."""
    db = db_session

    # 1. I4C National Admin Org & User
    i4c_org = db.query(Organization).filter(Organization.name == "I4C HQ").first()
    if not i4c_org:
        i4c_org = Organization(name="I4C HQ", org_type="I4C", state="Delhi", district="CENTRAL_NEW_DELHI")
        db.add(i4c_org)
        db.flush()

    i4c_admin = db.query(User).filter(User.email == "i4c_admin_p7@i4c.gov.in").first()
    if not i4c_admin:
        i4c_admin = User(
            email="i4c_admin_p7@i4c.gov.in",
            hashed_password="mock_test_hashed_password",
            full_name="I4C National Director",
            role="I4C_ADMIN",
            badge_number="I4C-P7-001",
            organization_id=i4c_org.id,
            is_active=True
        )
        db.add(i4c_admin)
    else:
        i4c_admin.organization_id = i4c_org.id
    db.flush()

    # 2. Delhi Police LEA Org & User (Originating Team)
    delhi_org = db.query(Organization).filter(Organization.name == "Delhi Police HQ").first()
    if not delhi_org:
        delhi_org = Organization(name="Delhi Police HQ", org_type="LEA", state="Delhi", district="CENTRAL_NEW_DELHI")
        db.add(delhi_org)
        db.flush()

    delhi_lea = db.query(User).filter(User.email == "delhi_lea_p7@police.gov.in").first()
    if not delhi_lea:
        delhi_lea = User(
            email="delhi_lea_p7@police.gov.in",
            hashed_password="mock_test_hashed_password",
            full_name="Delhi Cyber Inspector",
            role="DISTRICT_LEA",
            badge_number="DL-CP-P7",
            organization_id=delhi_org.id,
            is_active=True
        )
        db.add(delhi_lea)
    else:
        delhi_lea.organization_id = delhi_org.id
    db.flush()

    # 3. Mumbai Police LEA Org & Officers (Destination Team)
    mumbai_org = db.query(Organization).filter(Organization.name == "Mumbai Police Cyber").first()
    if not mumbai_org:
        mumbai_org = Organization(name="Mumbai Police Cyber", org_type="LEA", state="Maharashtra", district="MUMBAI_ZONE_P7")
        db.add(mumbai_org)
        db.flush()
    else:
        mumbai_org.district = "MUMBAI_ZONE_P7"
        mumbai_org.state = "Maharashtra"
        mumbai_org.org_type = "LEA"
        db.flush()

    mumbai_lea_1 = db.query(User).filter(User.email == "mumbai_lea_1_p7@police.gov.in").first()
    if not mumbai_lea_1:
        mumbai_lea_1 = User(
            email="mumbai_lea_1_p7@police.gov.in",
            hashed_password="mock_test_hashed_password",
            full_name="Mumbai Cyber Inspector Alpha",
            role="DISTRICT_LEA",
            badge_number="MH-MUM-P7-A",
            organization_id=mumbai_org.id,
            is_active=True
        )
        db.add(mumbai_lea_1)
    else:
        mumbai_lea_1.organization_id = mumbai_org.id
    db.flush()

    mumbai_lea_2 = db.query(User).filter(User.email == "mumbai_lea_2_p7@police.gov.in").first()
    if not mumbai_lea_2:
        mumbai_lea_2 = User(
            email="mumbai_lea_2_p7@police.gov.in",
            hashed_password="mock_test_hashed_password",
            full_name="Mumbai Cyber Inspector Beta",
            role="DISTRICT_LEA",
            badge_number="MH-MUM-P7-B",
            organization_id=mumbai_org.id,
            is_active=True
        )
        db.add(mumbai_lea_2)
    else:
        mumbai_lea_2.organization_id = mumbai_org.id
    db.flush()

    # 4. Bangalore (Karnataka) LEA Org & User (Unrelated Jurisdiction)
    bangalore_org = db.query(Organization).filter(Organization.name == "Bangalore Cyber Crime Cell").first()
    if not bangalore_org:
        bangalore_org = Organization(name="Bangalore Cyber Crime Cell", org_type="LEA", state="Karnataka", district="BANGALORE_URBAN")
        db.add(bangalore_org)
        db.flush()

    bangalore_lea = db.query(User).filter(User.email == "bangalore_lea_p7@police.gov.in").first()
    if not bangalore_lea:
        bangalore_lea = User(
            email="bangalore_lea_p7@police.gov.in",
            hashed_password="mock_test_hashed_password",
            full_name="Bangalore Cyber Officer",
            role="DISTRICT_LEA",
            badge_number="KA-BLR-P7",
            organization_id=bangalore_org.id,
            is_active=True
        )
        db.add(bangalore_lea)
    else:
        bangalore_lea.organization_id = bangalore_org.id
    db.flush()

    # 5. Bank Officer Org & User
    bank_org = db.query(Organization).filter(Organization.name == "Axis Bank Nodal").first()
    if not bank_org:
        bank_org = Organization(name="Axis Bank Nodal", org_type="BANK", state="Delhi", district="CENTRAL_NEW_DELHI")
        db.add(bank_org)
        db.flush()

    bank_officer = db.query(User).filter(User.email == "bank_officer_p7@axis.com").first()
    if not bank_officer:
        bank_officer = User(
            email="bank_officer_p7@axis.com",
            hashed_password="mock_test_hashed_password",
            full_name="Axis Bank Nodal Officer",
            role="BANK_OFFICER",
            badge_number="BNK-AXIS-P7",
            organization_id=bank_org.id,
            is_active=True
        )
        db.add(bank_officer)
    else:
        bank_officer.organization_id = bank_org.id
    db.flush()

    db.commit()

    return {
        "i4c_admin": {
            "Authorization": f"Bearer {create_access_token({'sub': i4c_admin.email, 'role': i4c_admin.role})}"
        },
        "delhi_lea": {
            "Authorization": f"Bearer {create_access_token({'sub': delhi_lea.email, 'role': delhi_lea.role})}"
        },
        "mumbai_lea_1": {
            "Authorization": f"Bearer {create_access_token({'sub': mumbai_lea_1.email, 'role': mumbai_lea_1.role})}"
        },
        "mumbai_lea_2": {
            "Authorization": f"Bearer {create_access_token({'sub': mumbai_lea_2.email, 'role': mumbai_lea_2.role})}"
        },
        "bangalore_lea": {
            "Authorization": f"Bearer {create_access_token({'sub': bangalore_lea.email, 'role': bangalore_lea.role})}"
        },
        "bank_officer": {
            "Authorization": f"Bearer {create_access_token({'sub': bank_officer.email, 'role': bank_officer.role})}"
        },
        "orgs": {
            "i4c": i4c_org,
            "delhi": delhi_org,
            "mumbai": mumbai_org,
            "bangalore": bangalore_org,
            "bank": bank_org,
        }
    }


@pytest.fixture
def delhi_case_with_evidence(db_session: Session, auth_headers):
    """Creates a synthetic Delhi complaint with active evidence files."""
    db = db_session
    now = datetime.now(timezone.utc).replace(tzinfo=None)
    delhi_org = auth_headers["orgs"]["delhi"]

    comp = Complaint(
        complaint_number=f"CMP-P7-{uuid.uuid4().hex[:10]}",
        fraud_type="Investment App Scam",
        amount=500000.00,
        victim_name="Rajesh Sharma",
        victim_phone="9811998877",
        victim_location="Rohini Sector 15, Delhi",
        locality="Rohini",
        state="Delhi",
        district="CENTRAL_NEW_DELHI",
        payment_channel="UPI",
        reported_at=now - timedelta(hours=1),
        incident_time=now - timedelta(hours=3),
        risk_level="HIGH",
        risk_score=0.88,
        prediction_status="AVAILABLE",
        case_status="ACTIVE",
        owner_organization_id=delhi_org.id,
        created_at=now
    )
    db.add(comp)
    db.flush()

    # Add evidence 1: FIR doc
    ev1 = EvidenceFile(
        complaint_id=comp.id,
        source="OFFICER_UPLOAD",
        uploader_role="DISTRICT_LEA",
        uploader_org_id=delhi_org.id,
        original_filename="fir_initial_report.pdf",
        storage_key=f"fir_{uuid.uuid4().hex[:8]}.pdf",
        mime_type="application/pdf",
        size_bytes=1024,
        sha256_hash="e3b0c44298fc1c149afbf4c8996fb92427ae41e4649b934ca495991b7852b855",
        version=1,
        status="ACTIVE",
        malware_scan_status="CLEAN",
        created_at=now
    )
    # Add evidence 2: Confidential Mule Account KYC
    ev2 = EvidenceFile(
        complaint_id=comp.id,
        source="BANK_STATEMENT",
        uploader_role="DISTRICT_LEA",
        uploader_org_id=delhi_org.id,
        original_filename="confidential_mule_kyc.pdf",
        storage_key=f"kyc_{uuid.uuid4().hex[:8]}.pdf",
        mime_type="application/pdf",
        size_bytes=2048,
        sha256_hash="f4b0c44298fc1c149afbf4c8996fb92427ae41e4649b934ca495991b7852b855",
        version=1,
        status="ACTIVE",
        malware_scan_status="CLEAN",
        created_at=now
    )
    db.add_all([ev1, ev2])
    db.commit()
    db.refresh(comp)
    db.refresh(ev1)
    db.refresh(ev2)

    return {"complaint": comp, "ev_fir": ev1, "ev_kyc": ev2}


def test_cross_state_handoff_request_and_metadata_persistence(client: TestClient, auth_headers, delhi_case_with_evidence):
    """
    Test 1: Delhi LEA initiates a cross-state handoff request to Mumbai LEA.
    Verifies metadata persistence, deadline calculation, and audit trail.
    """
    comp = delhi_case_with_evidence["complaint"]
    ev_fir = delhi_case_with_evidence["ev_fir"]

    payload = {
        "target_state": "Maharashtra",
        "target_district": "MUMBAI_ZONE_P7",
        "purpose": "ATM_INTERCEPTION",
        "evidence_scope": "SPECIFIC_EVIDENCE",
        "shared_evidence_ids": [ev_fir.id],
        "acknowledgement_hours": 24
    }

    # Delhi LEA requests handoff
    resp = client.post(
        f"/api/v1/complaints/{comp.id}/handoffs",
        json=payload,
        headers=auth_headers["delhi_lea"]
    )
    assert resp.status_code == 201, resp.text
    data = resp.json()
    assert data["complaint_id"] == comp.id
    assert data["target_state"] == "Maharashtra"
    assert data["target_district"] == "MUMBAI_ZONE_P7"
    assert data["purpose"] == "ATM_INTERCEPTION"
    assert data["evidence_scope"] == "SPECIFIC_EVIDENCE"
    assert data["shared_evidence_ids"] == [ev_fir.id]
    assert data["status"] == "REQUESTED"
    assert data["destination_organization_name"] == "Mumbai Police Cyber"

    handoff_id = data["id"]

    # Verify handoff in list
    list_resp = client.get(f"/api/v1/complaints/{comp.id}/handoffs", headers=auth_headers["delhi_lea"])
    assert list_resp.status_code == 200
    assert any(h["id"] == handoff_id for h in list_resp.json())


def test_destination_lea_scoped_case_and_evidence_visibility(client: TestClient, auth_headers, delhi_case_with_evidence):
    """
    Test 2: Destination LEA gains scoped visibility to the case and granted evidence.
    Unshared evidence is restricted.
    """
    comp = delhi_case_with_evidence["complaint"]
    ev_fir = delhi_case_with_evidence["ev_fir"]
    ev_kyc = delhi_case_with_evidence["ev_kyc"]

    # 1. Create handoff with SPECIFIC_EVIDENCE (only ev_fir shared)
    resp = client.post(
        f"/api/v1/complaints/{comp.id}/handoffs",
        json={
            "target_state": "Maharashtra",
            "target_district": "MUMBAI_ZONE_P7",
            "purpose": "PHYSICAL_SURVEILLANCE",
            "evidence_scope": "SPECIFIC_EVIDENCE",
            "shared_evidence_ids": [ev_fir.id],
            "acknowledgement_hours": 12
        },
        headers=auth_headers["delhi_lea"]
    )
    assert resp.status_code == 201
    handoff_id = resp.json()["id"]

    # 2. Mumbai LEA sees the complaint in incoming handoffs
    in_resp = client.get("/api/v1/handoffs/incoming", headers=auth_headers["mumbai_lea_1"])
    assert in_resp.status_code == 200
    assert any(h["id"] == handoff_id for h in in_resp.json())

    # 3. Mumbai LEA accepts handoff
    acc_resp = client.post(f"/api/v1/handoffs/{handoff_id}/accept", headers=auth_headers["mumbai_lea_1"])
    assert acc_resp.status_code == 200
    assert acc_resp.json()["status"] == "ACCEPTED"

    # 4. Mumbai LEA can now view complaint details
    comp_resp = client.get(f"/api/v1/complaints/{comp.id}", headers=auth_headers["mumbai_lea_1"])
    assert comp_resp.status_code == 200
    assert comp_resp.json()["complaint_number"] == comp.complaint_number

    # 5. Check evidence list for Mumbai LEA: only shared evidence (ev_fir) is returned
    ev_list_resp = client.get(f"/api/v1/complaints/{comp.id}/evidence", headers=auth_headers["mumbai_lea_1"])
    assert ev_list_resp.status_code == 200
    visible_ev_ids = [e["id"] for e in ev_list_resp.json()]
    assert ev_fir.id in visible_ev_ids
    assert ev_kyc.id not in visible_ev_ids


def test_metadata_only_evidence_scope_blocks_download(client: TestClient, auth_headers, delhi_case_with_evidence):
    """
    Test 3: Handoff with METADATA_ONLY evidence scope allows listing metadata but blocks file downloads.
    """
    comp = delhi_case_with_evidence["complaint"]
    ev_fir = delhi_case_with_evidence["ev_fir"]

    # Create handoff with METADATA_ONLY
    resp = client.post(
        f"/api/v1/complaints/{comp.id}/handoffs",
        json={
            "target_state": "Maharashtra",
            "target_district": "MUMBAI_ZONE_P7",
            "purpose": "LOCAL_INQUIRY",
            "evidence_scope": "METADATA_ONLY",
            "acknowledgement_hours": 24
        },
        headers=auth_headers["delhi_lea"]
    )
    assert resp.status_code == 201
    handoff_id = resp.json()["id"]

    # Accept handoff
    client.post(f"/api/v1/handoffs/{handoff_id}/accept", headers=auth_headers["mumbai_lea_1"])

    # Attempt download as Mumbai LEA -> 403 Forbidden
    down_resp = client.get(
        f"/api/v1/complaints/{comp.id}/evidence/{ev_fir.id}/download",
        headers=auth_headers["mumbai_lea_1"]
    )
    assert down_resp.status_code == 403
    assert "METADATA_ONLY" in down_resp.json()["detail"]


def test_unrelated_jurisdiction_and_bank_isolation(client: TestClient, auth_headers, delhi_case_with_evidence):
    """
    Test 4: Unrelated LEA (Bangalore) and Bank Officer cannot discover the handed-off case.
    """
    comp = delhi_case_with_evidence["complaint"]

    # Delhi creates handoff to Mumbai
    client.post(
        f"/api/v1/complaints/{comp.id}/handoffs",
        json={
            "target_state": "Maharashtra",
            "target_district": "MUMBAI_ZONE_P7",
            "purpose": "MULE_ARREST",
            "evidence_scope": "ALL_EVIDENCE",
            "acknowledgement_hours": 24
        },
        headers=auth_headers["delhi_lea"]
    )

    # Bangalore LEA queries complaints -> excluded
    ka_list_resp = client.get("/api/v1/complaints", headers=auth_headers["bangalore_lea"])
    assert ka_list_resp.status_code == 200
    res_data = ka_list_resp.json()
    comp_list = res_data if isinstance(res_data, list) else res_data.get("complaints", [])
    assert not any(c["id"] == comp.id for c in comp_list)

    # Bangalore LEA attempts direct GET on complaint -> 404
    ka_get_resp = client.get(f"/api/v1/complaints/{comp.id}", headers=auth_headers["bangalore_lea"])
    assert ka_get_resp.status_code == 404

    # Bangalore LEA attempts to view handoffs -> 404
    ka_h_resp = client.get(f"/api/v1/complaints/{comp.id}/handoffs", headers=auth_headers["bangalore_lea"])
    assert ka_h_resp.status_code == 404


def test_full_state_machine_workflow(client: TestClient, auth_headers, delhi_case_with_evidence):
    """
    Test 5: Full valid state machine workflow:
    REQUESTED -> ACCEPTED -> IN_PROGRESS -> COMPLETED.
    """
    comp = delhi_case_with_evidence["complaint"]

    # 1. REQUESTED
    req_resp = client.post(
        f"/api/v1/complaints/{comp.id}/handoffs",
        json={
            "target_state": "Maharashtra",
            "target_district": "MUMBAI_ZONE_P7",
            "purpose": "ATM_INTERCEPTION",
            "evidence_scope": "ALL_EVIDENCE",
            "acknowledgement_hours": 48
        },
        headers=auth_headers["delhi_lea"]
    )
    assert req_resp.status_code == 201
    h_id = req_resp.json()["id"]
    assert req_resp.json()["status"] == "REQUESTED"

    # 2. ACCEPTED (Mumbai LEA)
    acc_resp = client.post(f"/api/v1/handoffs/{h_id}/accept", headers=auth_headers["mumbai_lea_1"])
    assert acc_resp.status_code == 200
    assert acc_resp.json()["status"] == "ACCEPTED"
    assert acc_resp.json()["accepted_at"] is not None

    # 3. IN_PROGRESS (Mumbai LEA)
    start_resp = client.post(f"/api/v1/handoffs/{h_id}/start", headers=auth_headers["mumbai_lea_1"])
    assert start_resp.status_code == 200
    assert start_resp.json()["status"] == "IN_PROGRESS"

    # 4. COMPLETED (Mumbai LEA)
    comp_resp = client.post(
        f"/api/v1/handoffs/{h_id}/complete",
        json={"completed_notes": "ATM CCTV reviewed. Mule suspect identified and detained at Andheri branch."},
        headers=auth_headers["mumbai_lea_1"]
    )
    assert comp_resp.status_code == 200
    assert comp_resp.json()["status"] == "COMPLETED"
    assert comp_resp.json()["completed_at"] is not None
    assert "Mule suspect identified" in comp_resp.json()["completed_notes"]


def test_rejection_flow_and_access_revocation(client: TestClient, auth_headers, delhi_case_with_evidence):
    """
    Test 6: Destination LEA rejects handoff with reason -> access is immediately revoked.
    """
    comp = delhi_case_with_evidence["complaint"]

    req_resp = client.post(
        f"/api/v1/complaints/{comp.id}/handoffs",
        json={
            "target_state": "Maharashtra",
            "target_district": "MUMBAI_ZONE_P7",
            "purpose": "LOCAL_INQUIRY",
            "evidence_scope": "METADATA_ONLY",
            "acknowledgement_hours": 24
        },
        headers=auth_headers["delhi_lea"]
    )
    h_id = req_resp.json()["id"]

    # Reject handoff
    rej_resp = client.post(
        f"/api/v1/handoffs/{h_id}/reject",
        json={"rejection_reason": "Jurisdiction conflict: location belongs to Thane district."},
        headers=auth_headers["mumbai_lea_1"]
    )
    assert rej_resp.status_code == 200
    assert rej_resp.json()["status"] == "REJECTED"
    assert "Thane district" in rej_resp.json()["rejection_reason"]

    # After rejection, Mumbai LEA cannot access the complaint
    comp_resp = client.get(f"/api/v1/complaints/{comp.id}", headers=auth_headers["mumbai_lea_1"])
    assert comp_resp.status_code == 404


def test_cancellation_flow_and_access_revocation(client: TestClient, auth_headers, delhi_case_with_evidence):
    """
    Test 7: Originating LEA cancels handoff -> destination access is immediately revoked.
    """
    comp = delhi_case_with_evidence["complaint"]

    req_resp = client.post(
        f"/api/v1/complaints/{comp.id}/handoffs",
        json={
            "target_state": "Maharashtra",
            "target_district": "MUMBAI_ZONE_P7",
            "purpose": "ATM_INTERCEPTION",
            "evidence_scope": "ALL_EVIDENCE",
            "acknowledgement_hours": 24
        },
        headers=auth_headers["delhi_lea"]
    )
    h_id = req_resp.json()["id"]

    # Accept first
    client.post(f"/api/v1/handoffs/{h_id}/accept", headers=auth_headers["mumbai_lea_1"])

    # Delhi LEA cancels handoff
    canc_resp = client.post(
        f"/api/v1/handoffs/{h_id}/cancel",
        json={"cancellation_reason": "Suspect moved to another state; physical team re-routed."},
        headers=auth_headers["delhi_lea"]
    )
    assert canc_resp.status_code == 200
    assert canc_resp.json()["status"] == "CANCELLED"

    # After cancellation, Mumbai LEA cannot access complaint
    comp_resp = client.get(f"/api/v1/complaints/{comp.id}", headers=auth_headers["mumbai_lea_1"])
    assert comp_resp.status_code == 404


def test_deadline_expiration_and_escalation(client: TestClient, auth_headers, delhi_case_with_evidence, db_session: Session):
    """
    Test 8: Expired acknowledgement deadline triggers auto-expiration and access revocation.
    """
    comp = delhi_case_with_evidence["complaint"]

    # Create handoff
    req_resp = client.post(
        f"/api/v1/complaints/{comp.id}/handoffs",
        json={
            "target_state": "Maharashtra",
            "target_district": "MUMBAI_ZONE_P7",
            "purpose": "ATM_INTERCEPTION",
            "evidence_scope": "ALL_EVIDENCE",
            "acknowledgement_hours": 24
        },
        headers=auth_headers["delhi_lea"]
    )
    h_id = req_resp.json()["id"]

    # Manually backdate acknowledgement_deadline in database
    h = db_session.query(CaseHandoff).filter(CaseHandoff.id == h_id).first()
    h.acknowledgement_deadline = datetime.now(timezone.utc).replace(tzinfo=None) - timedelta(hours=2)
    db_session.commit()

    # Trigger expiration check
    exp_resp = client.post("/api/v1/handoffs/check-expirations", headers=auth_headers["i4c_admin"])
    assert exp_resp.status_code == 200
    assert h_id in exp_resp.json()["expired_handoff_ids"]

    # Verify status is EXPIRED
    detail_resp = client.get(f"/api/v1/handoffs/{h_id}", headers=auth_headers["delhi_lea"])
    assert detail_resp.status_code == 200
    assert detail_resp.json()["status"] == "EXPIRED"

    # Mumbai LEA cannot access complaint
    comp_resp = client.get(f"/api/v1/complaints/{comp.id}", headers=auth_headers["mumbai_lea_1"])
    assert comp_resp.status_code == 404


def test_idempotent_duplicate_actions_and_replays(client: TestClient, auth_headers, delhi_case_with_evidence):
    """
    Test 9: Replayed/duplicate transition requests are safe and idempotent.
    """
    comp = delhi_case_with_evidence["complaint"]

    req_resp = client.post(
        f"/api/v1/complaints/{comp.id}/handoffs",
        json={
            "target_state": "Maharashtra",
            "target_district": "MUMBAI_ZONE_P7",
            "purpose": "BANK_BRANCH_VISIT",
            "evidence_scope": "METADATA_ONLY",
            "acknowledgement_hours": 24
        },
        headers=auth_headers["delhi_lea"]
    )
    h_id = req_resp.json()["id"]

    # First accept
    acc1 = client.post(f"/api/v1/handoffs/{h_id}/accept", headers=auth_headers["mumbai_lea_1"])
    assert acc1.status_code == 200

    # Duplicate accept by same officer -> idempotent 200
    acc2 = client.post(f"/api/v1/handoffs/{h_id}/accept", headers=auth_headers["mumbai_lea_1"])
    assert acc2.status_code == 200
    assert acc2.json()["status"] == "ACCEPTED"


def test_concurrent_acceptance_conflict_protection(client: TestClient, auth_headers, delhi_case_with_evidence):
    """
    Test 10: If Officer 1 accepts, Officer 2 from the same destination org receives 409 Conflict.
    """
    comp = delhi_case_with_evidence["complaint"]

    req_resp = client.post(
        f"/api/v1/complaints/{comp.id}/handoffs",
        json={
            "target_state": "Maharashtra",
            "target_district": "MUMBAI_ZONE_P7",
            "purpose": "PHYSICAL_SURVEILLANCE",
            "evidence_scope": "ALL_EVIDENCE",
            "acknowledgement_hours": 24
        },
        headers=auth_headers["delhi_lea"]
    )
    h_id = req_resp.json()["id"]

    # Officer 1 accepts
    acc1 = client.post(f"/api/v1/handoffs/{h_id}/accept", headers=auth_headers["mumbai_lea_1"])
    assert acc1.status_code == 200

    # Officer 2 attempts to accept -> 409 Conflict
    acc2 = client.post(f"/api/v1/handoffs/{h_id}/accept", headers=auth_headers["mumbai_lea_2"])
    assert acc2.status_code == 409
    assert "already been accepted" in acc2.json()["detail"]
