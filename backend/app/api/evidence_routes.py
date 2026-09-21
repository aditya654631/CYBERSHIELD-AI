"""
CyberShield AI — Phase 6: Case Evidence Documentation & Storage Endpoints.
Enforces Phase 3 object-level jurisdiction access controls on all upload, list,
download, integrity-check, and replacement operations.
"""

import os
from typing import List, Optional
from fastapi import APIRouter, Depends, HTTPException, UploadFile, File, Form, status
from fastapi.responses import FileResponse
from sqlalchemy.orm import Session

from backend.app.models.db import get_db
from backend.app.models.models import Complaint, EvidenceFile, User
from backend.app.schemas.schemas import (
    EvidenceFileResponse, EvidenceIntegrityResponse, EvidenceScanUpdateRequest
)
from backend.app.auth.security import get_current_user
from backend.app.auth.rbac import (
    verify_complaint_access, require_roles, RoleEnum, is_national_scope,
    get_active_complaint_handoff
)
from backend.app.services.evidence_service import (
    upload_evidence, replace_evidence, verify_evidence_integrity,
    get_absolute_file_path, update_malware_scan
)
from backend.app.services.audit_service import log_audit


router = APIRouter(tags=["Evidence Documentation"])


def _resolve_and_verify_complaint(complaint_id_or_number: str, user: User, db: Session) -> Complaint:
    """Resolves complaint by ID or complaint_number and verifies caller's RBAC scope."""
    if complaint_id_or_number.isdigit():
        complaint = db.query(Complaint).filter(Complaint.id == int(complaint_id_or_number)).first()
    else:
        complaint = db.query(Complaint).filter(Complaint.complaint_number == complaint_id_or_number).first()
        
    if not complaint or not verify_complaint_access(complaint, user, db):
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="Complaint not found"
        )
    return complaint


@router.post(
    "/complaints/{complaint_id}/evidence",
    response_model=EvidenceFileResponse,
    status_code=status.HTTP_201_CREATED
)
def upload_complaint_evidence(
    complaint_id: str,
    file: UploadFile = File(...),
    source: str = Form("OFFICER_UPLOAD"),
    description: Optional[str] = Form(None),
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user)
):
    """
    Uploads a new tamper-evident digital evidence file for a complaint.
    Enforces Phase 3 object-level and jurisdictional authorization.
    """
    # AUDITOR is read-only
    if current_user.role == RoleEnum.AUDITOR:
        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN,
            detail="Auditor role is strictly read-only and cannot upload evidence."
        )

    complaint = _resolve_and_verify_complaint(complaint_id, current_user, db)

    evidence = upload_evidence(
        db=db,
        complaint_id=complaint.id,
        file=file,
        source=source,
        description=description,
        current_user=current_user
    )
    return evidence


@router.get(
    "/complaints/{complaint_id}/evidence",
    response_model=List[EvidenceFileResponse]
)
def list_complaint_evidence(
    complaint_id: str,
    include_superseded: bool = True,
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user)
):
    """
    Lists all evidence records associated with an authorized complaint.
    Enforces Phase 7 handoff evidence scope for destination organizations.
    """
    complaint = _resolve_and_verify_complaint(complaint_id, current_user, db)

    query = db.query(EvidenceFile).filter(EvidenceFile.complaint_id == complaint.id)
    if not include_superseded:
        query = query.filter(EvidenceFile.status == "ACTIVE")

    # Phase 7: If caller is accessing via handoff, apply evidence scoping
    is_native = (
        is_national_scope(current_user)
        or complaint.owner_organization_id == current_user.organization_id
        or (current_user.organization and (current_user.organization.state or "").strip().lower() == (complaint.state or "").strip().lower())
    )
    if not is_native:
        handoff = get_active_complaint_handoff(complaint.id, current_user, db)
        if handoff:
            if handoff.evidence_scope == "SPECIFIC_EVIDENCE":
                shared_ids = handoff.shared_evidence_ids or []
                query = query.filter(EvidenceFile.id.in_(shared_ids))
    
    evidence_list = query.order_by(EvidenceFile.version.asc(), EvidenceFile.id.asc()).all()

    # Log access audit
    log_audit(
        db=db,
        user_id=current_user.id,
        officer_name=current_user.full_name,
        role=current_user.role,
        action="EVIDENCE_ACCESSED",
        case_number=complaint.complaint_number,
        details=f"Listed {len(evidence_list)} evidence records for Case #{complaint.complaint_number}."
    )

    return evidence_list


@router.get(
    "/complaints/{complaint_id}/evidence/{evidence_id}",
    response_model=EvidenceFileResponse
)
@router.get(
    "/evidence/{evidence_id}",
    response_model=EvidenceFileResponse
)
def get_evidence_detail(
    evidence_id: int,
    complaint_id: Optional[str] = None,
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user)
):
    """
    Retrieves evidence metadata and performs caller authorization check.
    """
    evidence = db.query(EvidenceFile).filter(EvidenceFile.id == evidence_id).first()
    if not evidence:
        raise HTTPException(status_code=404, detail="Evidence file not found")

    complaint = db.query(Complaint).filter(Complaint.id == evidence.complaint_id).first()
    if not complaint or not verify_complaint_access(complaint, current_user, db):
        raise HTTPException(status_code=404, detail="Evidence file not found")

    # If complaint_id query param was passed, verify it matches
    if complaint_id:
        scoped_comp = _resolve_and_verify_complaint(complaint_id, current_user, db)
        if scoped_comp.id != evidence.complaint_id:
            raise HTTPException(status_code=404, detail="Evidence file not found under this case")

    is_native = (
        is_national_scope(current_user)
        or complaint.owner_organization_id == current_user.organization_id
        or (current_user.organization and (current_user.organization.state or "").strip().lower() == (complaint.state or "").strip().lower())
    )
    if not is_native:
        handoff = get_active_complaint_handoff(complaint.id, current_user, db)
        if handoff and handoff.evidence_scope == "SPECIFIC_EVIDENCE":
            if evidence.id not in (handoff.shared_evidence_ids or []):
                raise HTTPException(status_code=404, detail="Evidence file not in granted scope")

    return evidence


@router.get("/complaints/{complaint_id}/evidence/{evidence_id}/download")
@router.get("/evidence/{evidence_id}/download")
def download_evidence_file(
    evidence_id: int,
    complaint_id: Optional[str] = None,
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user)
):
    """
    Serves evidence file download as attachment with strict SHA-256 integrity verification.
    """
    evidence = db.query(EvidenceFile).filter(EvidenceFile.id == evidence_id).first()
    if not evidence:
        raise HTTPException(status_code=404, detail="Evidence file not found")

    complaint = db.query(Complaint).filter(Complaint.id == evidence.complaint_id).first()
    if not complaint or not verify_complaint_access(complaint, current_user, db):
        raise HTTPException(status_code=404, detail="Evidence file not found")

    if complaint_id:
        scoped_comp = _resolve_and_verify_complaint(complaint_id, current_user, db)
        if scoped_comp.id != evidence.complaint_id:
            raise HTTPException(status_code=404, detail="Evidence file not found under this case")

    # Phase 7: Scope restriction on download
    is_native = (
        is_national_scope(current_user)
        or complaint.owner_organization_id == current_user.organization_id
        or (current_user.organization and (current_user.organization.state or "").strip().lower() == (complaint.state or "").strip().lower())
    )
    if not is_native:
        handoff = get_active_complaint_handoff(complaint.id, current_user, db)
        if handoff:
            if handoff.evidence_scope == "METADATA_ONLY":
                raise HTTPException(
                    status_code=status.HTTP_403_FORBIDDEN,
                    detail="Access to file content is restricted by handoff evidence scope (METADATA_ONLY)."
                )
            if handoff.evidence_scope == "SPECIFIC_EVIDENCE":
                if evidence.id not in (handoff.shared_evidence_ids or []):
                    raise HTTPException(
                        status_code=status.HTTP_403_FORBIDDEN,
                        detail="Evidence file is not included in the granted handoff scope."
                    )

    # Verify cryptographic SHA-256 integrity before serving
    integrity = verify_evidence_integrity(evidence, db, current_user)
    if not integrity.get("is_valid"):
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail="Evidence file integrity violation: SHA-256 hash mismatch detected. Storage file may have been altered."
        )

    file_path = get_absolute_file_path(evidence.storage_key)
    if not os.path.exists(file_path):
        raise HTTPException(status_code=404, detail="Evidence file missing on disk")

    # Log download audit event
    log_audit(
        db=db,
        user_id=current_user.id,
        officer_name=current_user.full_name,
        role=current_user.role,
        action="EVIDENCE_DOWNLOADED",
        case_number=complaint.complaint_number,
        details=f"Downloaded evidence #{evidence.id} ('{evidence.original_filename}', v{evidence.version}) under Case #{complaint.complaint_number}."
    )

    # Safe attachment header
    safe_filename = evidence.original_filename.replace('"', '').replace('\n', '').replace('\r', '')
    headers = {
        "Content-Disposition": f'attachment; filename="{safe_filename}"',
        "X-Content-Type-Options": "nosniff",
        "X-Evidence-SHA256": evidence.sha256_hash,
        "X-Evidence-Version": str(evidence.version)
    }

    return FileResponse(
        path=file_path,
        media_type=evidence.mime_type,
        headers=headers,
        filename=safe_filename
    )


@router.post(
    "/complaints/{complaint_id}/evidence/{evidence_id}/replace",
    response_model=EvidenceFileResponse
)
def replace_complaint_evidence(
    complaint_id: str,
    evidence_id: int,
    file: UploadFile = File(...),
    description: Optional[str] = Form(None),
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user)
):
    """
    Replaces existing evidence with an updated version (v+1).
    Preserves original evidence version as SUPERSEDED.
    """
    if current_user.role == RoleEnum.AUDITOR:
        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN,
            detail="Auditor role is strictly read-only and cannot replace evidence."
        )

    complaint = _resolve_and_verify_complaint(complaint_id, current_user, db)

    evidence = db.query(EvidenceFile).filter(EvidenceFile.id == evidence_id).first()
    if not evidence or evidence.complaint_id != complaint.id:
        raise HTTPException(status_code=404, detail="Evidence file not found under this case")

    new_evidence = replace_evidence(
        db=db,
        existing_evidence_id=evidence.id,
        file=file,
        description=description,
        current_user=current_user
    )
    return new_evidence


@router.get(
    "/complaints/{complaint_id}/evidence/{evidence_id}/integrity",
    response_model=EvidenceIntegrityResponse
)
@router.get(
    "/evidence/{evidence_id}/integrity",
    response_model=EvidenceIntegrityResponse
)
def check_evidence_integrity(
    evidence_id: int,
    complaint_id: Optional[str] = None,
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user)
):
    """
    Performs on-demand SHA-256 cryptographic integrity verification.
    """
    evidence = db.query(EvidenceFile).filter(EvidenceFile.id == evidence_id).first()
    if not evidence:
        raise HTTPException(status_code=404, detail="Evidence file not found")

    complaint = db.query(Complaint).filter(Complaint.id == evidence.complaint_id).first()
    if not complaint or not verify_complaint_access(complaint, current_user, db):
        raise HTTPException(status_code=404, detail="Evidence file not found")

    return verify_evidence_integrity(evidence, db, current_user)


@router.post(
    "/evidence/{evidence_id}/scan-status",
    response_model=EvidenceFileResponse
)
def set_evidence_scan_status(
    evidence_id: int,
    data: EvidenceScanUpdateRequest,
    db: Session = Depends(get_db),
    current_user: User = Depends(require_roles(RoleEnum.I4C_ADMIN))
):
    """
    Updates malware scanning status. Restricted to I4C_ADMIN or security automation.
    """
    return update_malware_scan(
        db=db,
        evidence_id=evidence_id,
        status_val=data.status,
        details=data.details,
        current_user=current_user
    )
