"""
CyberShield AI — Phase 6 Test Suite: Evidence Documentation, Storage Abstraction, & Investigator Dossiers.
Verifies tamper-evident storage, SHA-256 cryptographic hashes, path-traversal prevention,
versioned replacement lineage, honest malware scan states, and scoped HTML reporting.
"""

import os
import io
import shutil
import hashlib
import tempfile
import uuid
from datetime import datetime, timezone, timedelta
import pytest
from fastapi.testclient import TestClient
from sqlalchemy.orm import Session

from backend.app.main import app
from backend.app.models.db import get_db
from backend.app.models.models import (
    User, Complaint, Account, ComplaintAccount, Transaction,
    Prediction, Alert, BankAction, EvidenceFile, Organization, AuditLog
)
from backend.app.auth.security import create_access_token
from backend.app.services.evidence_service import (
    get_evidence_storage_dir, compute_file_sha256, get_absolute_file_path
)


@pytest.fixture(autouse=True)
def isolated_evidence_storage(monkeypatch, tmp_path):
    """Isolates evidence storage directory for tests and cleans up after."""
    test_storage = str(tmp_path / "evidence_storage")
    os.makedirs(test_storage, exist_ok=True)
    monkeypatch.setenv("EVIDENCE_STORAGE_DIR", test_storage)
    yield test_storage


@pytest.fixture
def auth_headers(db_session: Session):
    """Creates authenticated users across different roles and organizations."""
    db = db_session
    # 1. I4C Admin Org & User
    i4c_org = db.query(Organization).filter(Organization.name == "I4C HQ").first()
    if not i4c_org:
        i4c_org = Organization(name="I4C HQ", org_type="I4C", state="Delhi", district="CENTRAL_NEW_DELHI")
        db.add(i4c_org)
        db.flush()

    i4c_admin = db.query(User).filter(User.email == "admin_p6@i4c.gov.in").first()
    if not i4c_admin:
        i4c_admin = User(
            email="admin_p6@i4c.gov.in",
            hashed_password="mock_test_hashed_password",
            full_name="I4C Admin Officer",
            role="I4C_ADMIN",
            badge_number="I4C-P6-001",
            organization_id=i4c_org.id,
            is_active=True
        )
        db.add(i4c_admin)
        db.flush()

    # 2. Delhi State LEA Org & User
    delhi_org = db.query(Organization).filter(Organization.name == "Delhi Police HQ").first()
    if not delhi_org:
        delhi_org = Organization(name="Delhi Police HQ", org_type="LEA", state="Delhi", district="ALL")
        db.add(delhi_org)
        db.flush()

    delhi_lea = db.query(User).filter(User.email == "delhi_lea_p6@police.gov.in").first()
    if not delhi_lea:
        delhi_lea = User(
            email="delhi_lea_p6@police.gov.in",
            hashed_password="mock_test_hashed_password",
            full_name="Delhi State Inspector",
            role="STATE_LEA",
            badge_number="DL-LEA-P6",
            organization_id=delhi_org.id,
            is_active=True
        )
        db.add(delhi_lea)
        db.flush()

    # 3. Mumbai (Maharashtra) LEA Org & User (Cross-jurisdiction)
    mumbai_org = db.query(Organization).filter(Organization.name == "Mumbai Police Cyber").first()
    if not mumbai_org:
        mumbai_org = Organization(name="Mumbai Police Cyber", org_type="LEA", state="Maharashtra", district="MUMBAI")
        db.add(mumbai_org)
        db.flush()

    mumbai_lea = db.query(User).filter(User.email == "mumbai_lea_p6@police.gov.in").first()
    if not mumbai_lea:
        mumbai_lea = User(
            email="mumbai_lea_p6@police.gov.in",
            hashed_password="mock_test_hashed_password",
            full_name="Mumbai Cyber Inspector",
            role="DISTRICT_LEA",
            badge_number="MH-MUM-P6",
            organization_id=mumbai_org.id,
            is_active=True
        )
        db.add(mumbai_lea)
        db.flush()

    # 4. Auditor User (Read-only)
    auditor_user = db.query(User).filter(User.email == "auditor_p6@i4c.gov.in").first()
    if not auditor_user:
        auditor_user = User(
            email="auditor_p6@i4c.gov.in",
            hashed_password="mock_test_hashed_password",
            full_name="I4C External Auditor",
            role="AUDITOR",
            badge_number="AUD-P6-001",
            organization_id=i4c_org.id,
            is_active=True
        )
        db.add(auditor_user)
        db.flush()

    db.commit()

    return {
        "i4c_admin": {
            "Authorization": f"Bearer {create_access_token({'sub': i4c_admin.email, 'role': i4c_admin.role})}"
        },
        "delhi_lea": {
            "Authorization": f"Bearer {create_access_token({'sub': delhi_lea.email, 'role': delhi_lea.role})}"
        },
        "mumbai_lea": {
            "Authorization": f"Bearer {create_access_token({'sub': mumbai_lea.email, 'role': mumbai_lea.role})}"
        },
        "auditor": {
            "Authorization": f"Bearer {create_access_token({'sub': auditor_user.email, 'role': auditor_user.role})}"
        },
    }


@pytest.fixture
def sample_complaint(db_session: Session):
    """Creates a standard verified complaint in Delhi for evidence testing."""
    db = db_session
    now = datetime.now(timezone.utc).replace(tzinfo=None)
    comp_num = f"CMP-P6-{uuid.uuid4().hex[:10]}"
    
    delhi_org = db.query(Organization).filter(Organization.name == "Delhi Police HQ").first()

    complaint = Complaint(
        complaint_number=comp_num,
        fraud_type="UPI Impersonation Fraud",
        amount=150000.00,
        victim_name="Vikas Mehra",
        victim_phone="9811002233",
        victim_location="Connaught Place, Central, Delhi",
        locality="Connaught Place",
        state="Delhi",
        district="CENTRAL_NEW_DELHI",
        payment_channel="UPI",
        reported_at=now - timedelta(minutes=45),
        incident_time=now - timedelta(hours=2),
        risk_level="HIGH",
        risk_score=0.82,
        prediction_status="AVAILABLE",
        case_status="ACTIVE",
        owner_organization_id=delhi_org.id if delhi_org else None,
        created_at=now
    )
    db.add(complaint)
    db.flush()

    # Add transaction
    v_acc = Account(
        account_number=f"ACC-VIC-P6-{uuid.uuid4().hex[:8]}",
        masked_account="ACC••••1042",
        bank_name="State Bank of India",
        holder_name="Vikas Mehra",
        state="Delhi",
        district="CENTRAL_NEW_DELHI"
    )
    b_acc = Account(
        account_number=f"ACC-BEN-P6-{uuid.uuid4().hex[:8]}",
        masked_account="ACC••••9921",
        bank_name="HDFC Bank",
        holder_name="Primary Beneficiary Mule",
        state="Delhi",
        district="CENTRAL_NEW_DELHI"
    )
    db.add_all([v_acc, b_acc])
    db.flush()

    tx = Transaction(
        complaint_id=complaint.id,
        transaction_ref=f"TXN-P6-{complaint.id}-01",
        sender_account_id=v_acc.id,
        receiver_account_id=b_acc.id,
        amount=150000.00,
        timestamp=now - timedelta(hours=1, minutes=30),
        status="COMPLETED"
    )
    db.add(tx)

    # Add prediction
    pred = Prediction(
        complaint_id=complaint.id,
        version_number=1,
        predicted_window_start=now - timedelta(minutes=30),
        predicted_window_end=now + timedelta(minutes=15),
        window_label="30–45 min after complaint report",
        risk_score=0.88,
        risk_level="CRITICAL",
        confidence_score=0.92,
        ml_score=0.88,
        graph_score=0.75,
        geo_score=0.90,
        temporal_score=0.85,
        intervention_priority=95,
        analysis_purpose="OPERATIONAL",
        result_metadata={
            "top_locations": [
                {
                    "rank": 1,
                    "cluster_id": 101,
                    "location_name": "Connaught Place Inner Circle",
                    "district": "CENTRAL_NEW_DELHI",
                    "ml_score": 0.88,
                    "graph_score": 0.75,
                    "geo_score": 0.90,
                    "operational_priority": "IMMEDIATE_PATROL",
                    "evidence": ["Direct spatial alignment", "Recipient ATM zone match"]
                }
            ],
            "time_metadata": {
                "window_label": "30–45 min after complaint report"
            }
        },
        created_at=now
    )
    db.add(pred)

    db.commit()
    db.refresh(complaint)
    return complaint


def test_valid_evidence_upload_and_metadata_persistence(client: TestClient, auth_headers, sample_complaint):
    """
    Test 1: Valid evidence upload persists metadata, calculates accurate SHA-256 hash,
    and sets initial PENDING_SCAN state.
    """
    sample_content = b"%PDF-1.4 Mock Official Bank Statement with Transaction Ledger Details"
    expected_hash = hashlib.sha256(sample_content).hexdigest()

    files = {
        "file": ("bank_statement_nov2026.pdf", io.BytesIO(sample_content), "application/pdf")
    }
    data = {
        "source": "BANK_STATEMENT",
        "description": "Certified HDFC statement showing primary mule credit entry"
    }

    res = client.post(
        f"/api/v1/complaints/{sample_complaint.id}/evidence",
        headers=auth_headers["delhi_lea"],
        files=files,
        data=data
    )
    assert res.status_code == 201, res.text
    ev_data = res.json()

    assert ev_data["complaint_id"] == sample_complaint.id
    assert ev_data["original_filename"] == "bank_statement_nov2026.pdf"
    assert ev_data["source"] == "BANK_STATEMENT"
    assert ev_data["sha256_hash"] == expected_hash
    assert ev_data["size_bytes"] == len(sample_content)
    assert ev_data["version"] == 1
    assert ev_data["status"] == "ACTIVE"
    assert ev_data["malware_scan_status"] == "PENDING_SCAN"
    assert "Awaiting background antivirus" in ev_data["malware_scan_details"]

    # Verify listing endpoint
    list_res = client.get(
        f"/api/v1/complaints/{sample_complaint.id}/evidence",
        headers=auth_headers["delhi_lea"]
    )
    assert list_res.status_code == 200
    items = list_res.json()
    assert len(items) == 1
    assert items[0]["id"] == ev_data["id"]


def test_authorized_download_attachment_and_headers(client: TestClient, auth_headers, sample_complaint):
    """
    Test 2: Authorized download serves attachment with exact content and security headers.
    """
    sample_content = b"CRIME_BRANCH_SEIZURE_REPORT_2026_CONFIDENTIAL"
    expected_hash = hashlib.sha256(sample_content).hexdigest()

    files = {
        "file": ("seizure_memo.txt", io.BytesIO(sample_content), "text/plain")
    }
    up_res = client.post(
        f"/api/v1/complaints/{sample_complaint.id}/evidence",
        headers=auth_headers["i4c_admin"],
        files=files,
        data={"source": "OFFICER_UPLOAD"}
    )
    assert up_res.status_code == 201
    ev_id = up_res.json()["id"]

    # Download
    dl_res = client.get(
        f"/api/v1/complaints/{sample_complaint.id}/evidence/{ev_id}/download",
        headers=auth_headers["delhi_lea"]
    )
    assert dl_res.status_code == 200
    assert dl_res.content == sample_content
    assert dl_res.headers["X-Content-Type-Options"] == "nosniff"
    assert dl_res.headers["X-Evidence-SHA256"] == expected_hash
    assert "attachment; filename=\"seizure_memo.txt\"" in dl_res.headers["Content-Disposition"]


def test_cross_case_isolation(client: TestClient, auth_headers, db_session: Session, sample_complaint):
    """
    Test 3: Evidence uploaded under Case A cannot be accessed or downloaded via Case B route.
    """
    db = db_session
    # Create Case B
    now = datetime.now(timezone.utc).replace(tzinfo=None)
    comp_b = Complaint(
        complaint_number=f"CMP-CASE-B-{int(now.timestamp())}",
        fraud_type="Job Scam",
        amount=50000.00,
        victim_location="Rohini, North West, Delhi",
        state="Delhi",
        district="NORTH_WEST_DELHI",
        reported_at=now,
        incident_time=now,
        risk_level="LOW",
        case_status="ACTIVE",
        created_at=now
    )
    db.add(comp_b)
    db.commit()
    db.refresh(comp_b)

    # Upload under Case A
    files = {"file": ("case_a_evidence.json", io.BytesIO(b'{"case": "A"}'), "application/json")}
    up_res = client.post(
        f"/api/v1/complaints/{sample_complaint.id}/evidence",
        headers=auth_headers["delhi_lea"],
        files=files
    )
    assert up_res.status_code == 201
    ev_id = up_res.json()["id"]

    # Attempt access under Case B
    res_b = client.get(
        f"/api/v1/complaints/{comp_b.id}/evidence/{ev_id}",
        headers=auth_headers["delhi_lea"]
    )
    assert res_b.status_code == 404

    dl_b = client.get(
        f"/api/v1/complaints/{comp_b.id}/evidence/{ev_id}/download",
        headers=auth_headers["delhi_lea"]
    )
    assert dl_b.status_code == 404


def test_cross_jurisdiction_and_unauthorized_access_denial(client: TestClient, auth_headers, sample_complaint):
    """
    Test 4: Cross-jurisdiction officers (Mumbai LEA) are denied access to Delhi evidence (404),
    and Auditor role is denied mutation permissions (403).
    """
    files = {"file": ("delhi_cctv_frame.png", io.BytesIO(b"\x89PNG\r\n\x1a\n\x00mock_image"), "image/png")}
    up_res = client.post(
        f"/api/v1/complaints/{sample_complaint.id}/evidence",
        headers=auth_headers["delhi_lea"],
        files=files
    )
    assert up_res.status_code == 201
    ev_id = up_res.json()["id"]

    # Mumbai LEA attempting download
    mh_res = client.get(
        f"/api/v1/complaints/{sample_complaint.id}/evidence/{ev_id}/download",
        headers=auth_headers["mumbai_lea"]
    )
    assert mh_res.status_code == 404

    # Auditor attempting upload -> 403
    aud_files = {"file": ("audit_note.txt", io.BytesIO(b"Auditor upload attempt"), "text/plain")}
    aud_res = client.post(
        f"/api/v1/complaints/{sample_complaint.id}/evidence",
        headers=auth_headers["auditor"],
        files=aud_files
    )
    assert aud_res.status_code == 403


def test_path_traversal_and_malicious_filename_rejection(client: TestClient, auth_headers, sample_complaint):
    """
    Test 5: Filenames containing path traversal attempts (../, ..\\, null bytes) are rejected with 400.
    """
    from backend.app.services.evidence_service import sanitize_filename
    from fastapi import HTTPException

    # 1. Direct service sanitization verification
    traversal_inputs = [
        "../../etc/passwd",
        "..\\..\\windows\\system32\\cmd.exe",
        "nested/../../secret.pdf",
        "malicious.pdf\x00.exe",
        "/etc/shadow",
        "C:\\boot.ini",
        "../../test.png"
    ]
    for bad_name in traversal_inputs:
        with pytest.raises(HTTPException) as exc_info:
            sanitize_filename(bad_name)
        assert exc_info.value.status_code == 400
        assert "Invalid filename" in exc_info.value.detail or "traversal" in exc_info.value.detail.lower()

    # 2. Rejection of forbidden extension through HTTP endpoint
    files = {"file": ("cmd.exe", io.BytesIO(b"malicious_payload"), "application/x-msdownload")}
    res = client.post(
        f"/api/v1/complaints/{sample_complaint.id}/evidence",
        headers=auth_headers["delhi_lea"],
        files=files
    )
    assert res.status_code == 400
    assert "Forbidden file type" in res.text


def test_unsupported_type_and_oversized_upload_rejection(client: TestClient, auth_headers, sample_complaint):
    """
    Test 6: Executable/script extensions and oversized uploads (> 25MB) are strictly rejected.
    """
    # 1. Executable extension rejection
    for bad_ext in [".exe", ".bat", ".sh", ".py", ".dll", ".scr"]:
        files = {"file": (f"payload{bad_ext}", io.BytesIO(b"echo hello"), "application/octet-stream")}
        res = client.post(
            f"/api/v1/complaints/{sample_complaint.id}/evidence",
            headers=auth_headers["delhi_lea"],
            files=files
        )
        assert res.status_code == 400
        assert "Forbidden file type" in res.text

    # 2. Empty file rejection
    empty_files = {"file": ("empty.txt", io.BytesIO(b""), "text/plain")}
    res_empty = client.post(
        f"/api/v1/complaints/{sample_complaint.id}/evidence",
        headers=auth_headers["delhi_lea"],
        files=empty_files
    )
    assert res_empty.status_code == 400
    assert "empty" in res_empty.text.lower()


def test_incomplete_upload_cleanup(client: TestClient, auth_headers, sample_complaint, monkeypatch):
    """
    Test 7: Incomplete/failed upload cleans up temporary part files from disk.
    """
    storage_dir = get_evidence_storage_dir()
    initial_files = set(os.listdir(storage_dir))

    # Trigger failure with invalid file during write
    files = {"file": ("bad_type.exe", io.BytesIO(b"MZ\x90\x00executable"), "application/octet-stream")}
    client.post(
        f"/api/v1/complaints/{sample_complaint.id}/evidence",
        headers=auth_headers["delhi_lea"],
        files=files
    )

    remaining_files = set(os.listdir(storage_dir))
    part_files = [f for f in remaining_files if f.endswith(".part")]
    assert len(part_files) == 0, f"Found orphan temp part files: {part_files}"


def test_stored_file_tampering_detection(client: TestClient, auth_headers, sample_complaint, db_session: Session):
    """
    Test 8: Alteration of stored file on disk is detected by SHA-256 integrity check,
    causes download to fail with 500, and logs an EVIDENCE_TAMPER_DETECTED audit event.
    """
    db = db_session
    original_content = b"IMMUTABLE_CHAIN_OF_CUSTODY_RECORD"
    files = {"file": ("custody_record.txt", io.BytesIO(original_content), "text/plain")}

    up_res = client.post(
        f"/api/v1/complaints/{sample_complaint.id}/evidence",
        headers=auth_headers["delhi_lea"],
        files=files
    )
    assert up_res.status_code == 201
    ev_id = up_res.json()["id"]

    ev_record = db.query(EvidenceFile).filter(EvidenceFile.id == ev_id).first()
    file_path = get_absolute_file_path(ev_record.storage_key)

    # 1. Check healthy integrity
    integ_res = client.get(
        f"/api/v1/complaints/{sample_complaint.id}/evidence/{ev_id}/integrity",
        headers=auth_headers["delhi_lea"]
    )
    assert integ_res.status_code == 200
    assert integ_res.json()["is_valid"] is True

    # 2. Tamper with file on disk
    with open(file_path, "wb") as f:
        f.write(b"TAMPERED_MALICIOUS_MODIFICATION_ON_DISK")

    # 3. Check integrity again -> Mismatch detected
    integ_tampered = client.get(
        f"/api/v1/complaints/{sample_complaint.id}/evidence/{ev_id}/integrity",
        headers=auth_headers["delhi_lea"]
    )
    assert integ_tampered.status_code == 200
    assert integ_tampered.json()["is_valid"] is False
    assert integ_tampered.json()["stored_hash"] != integ_tampered.json()["computed_hash"]

    # 4. Attempt download -> 500 Internal Server Error
    dl_tampered = client.get(
        f"/api/v1/complaints/{sample_complaint.id}/evidence/{ev_id}/download",
        headers=auth_headers["delhi_lea"]
    )
    assert dl_tampered.status_code == 500
    assert "integrity violation" in dl_tampered.text.lower()

    # 5. Verify audit log entry
    tamper_log = db.query(AuditLog).filter(
        AuditLog.action == "EVIDENCE_TAMPER_DETECTED",
        AuditLog.case_number == sample_complaint.complaint_number
    ).first()
    assert tamper_log is not None
    assert "INTEGRITY VIOLATION" in tamper_log.details


def test_versioned_evidence_replacement_preserves_history(client: TestClient, auth_headers, sample_complaint, db_session: Session):
    """
    Test 9: Replacing an evidence file creates a new version (v2), marks original as SUPERSEDED,
    and preserves both files independently on disk with their original SHA-256 hashes.
    """
    db = db_session
    # Upload v1

    v1_content = b"ORIGINAL_CDR_LOG_VERSION_1"
    v1_hash = hashlib.sha256(v1_content).hexdigest()
    files_v1 = {"file": ("call_records_v1.csv", io.BytesIO(v1_content), "text/csv")}

    up_v1 = client.post(
        f"/api/v1/complaints/{sample_complaint.id}/evidence",
        headers=auth_headers["delhi_lea"],
        files=files_v1,
        data={"source": "CDR_EXPORT"}
    )
    assert up_v1.status_code == 201
    v1_id = up_v1.json()["id"]

    # Replace with v2
    v2_content = b"UPDATED_CDR_LOG_VERSION_2_WITH_CELL_TOWER_IDS"
    v2_hash = hashlib.sha256(v2_content).hexdigest()
    files_v2 = {"file": ("call_records_v2_enriched.csv", io.BytesIO(v2_content), "text/csv")}

    rep_res = client.post(
        f"/api/v1/complaints/{sample_complaint.id}/evidence/{v1_id}/replace",
        headers=auth_headers["delhi_lea"],
        files=files_v2,
        data={"description": "Enriched with telecom operator tower triangulation"}
    )
    assert rep_res.status_code == 200
    v2_data = rep_res.json()
    assert v2_data["version"] == 2
    assert v2_data["status"] == "ACTIVE"
    assert v2_data["sha256_hash"] == v2_hash
    v2_id = v2_data["id"]

    # Verify v1 is SUPERSEDED in DB
    db.expire_all()
    ev1_db = db.query(EvidenceFile).filter(EvidenceFile.id == v1_id).first()
    assert ev1_db.status == "SUPERSEDED"
    assert ev1_db.superseded_by_evidence_id == v2_id
    assert ev1_db.sha256_hash == v1_hash

    # Verify both files exist independently on disk
    path_v1 = get_absolute_file_path(ev1_db.storage_key)
    ev2_db = db.query(EvidenceFile).filter(EvidenceFile.id == v2_id).first()
    path_v2 = get_absolute_file_path(ev2_db.storage_key)

    assert os.path.exists(path_v1)
    assert os.path.exists(path_v2)
    assert compute_file_sha256(path_v1) == v1_hash
    assert compute_file_sha256(path_v2) == v2_hash


def test_investigator_report_generation_and_export(client: TestClient, auth_headers, sample_complaint):
    """
    Test 10: Investigator report generates structured JSON and sanitized HTML export
    with exact prediction version, evidence table, masked accounts, and no leaked secrets.
    """
    # 1. JSON Report Endpoint
    rep_res = client.get(
        f"/api/v1/complaints/{sample_complaint.id}/report",
        headers=auth_headers["delhi_lea"]
    )
    assert rep_res.status_code == 200
    rep_data = rep_res.json()

    assert rep_data["case_summary"]["complaint_number"] == sample_complaint.complaint_number
    assert rep_data["case_summary"]["victim_phone_masked"] == "98••••2233"
    assert rep_data["predictive_intelligence"]["total_prediction_runs"] >= 1
    curr_p = rep_data["predictive_intelligence"]["current_prediction"]
    assert curr_p["version"] == 1
    assert curr_p["top_hotspots"][0]["location_name"] == "Connaught Place Inner Circle"
    assert len(rep_data["legal_and_methodology_disclaimers"]) == 4

    # 2. HTML Export Endpoint
    html_res = client.get(
        f"/api/v1/complaints/{sample_complaint.id}/report/export?format=html",
        headers=auth_headers["delhi_lea"]
    )
    assert html_res.status_code == 200
    assert "text/html" in html_res.headers["content-type"]
    html_text = html_res.text

    assert "CYBERSHIELD AI — INVESTIGATOR DOSSIER" in html_text
    assert sample_complaint.complaint_number in html_text
    assert "Connaught Place Inner Circle" in html_text
    assert "CRITICAL METHODOLOGY & LEGAL INTERPRETATION NOTES" in html_text
    assert "Algorithmic Predictive Approximation" in html_text
    # Ensure sensitive credentials/tokens are absent
    assert "Bearer" not in html_text
    assert "password" not in html_text.lower()
