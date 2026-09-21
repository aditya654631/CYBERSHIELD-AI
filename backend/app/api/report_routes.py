"""
CyberShield AI — Phase 6: Scoped Investigator Report & Export Endpoints.
Generates structured JSON and XSS-safe HTML investigator dossiers for law enforcement officers.
"""

from typing import Optional
from fastapi import APIRouter, Depends, HTTPException, Query, Response, status
from fastapi.responses import HTMLResponse
from sqlalchemy.orm import Session

from backend.app.models.db import get_db
from backend.app.models.models import Complaint, User
from backend.app.schemas.schemas import InvestigatorReportDataResponse
from backend.app.auth.security import get_current_user
from backend.app.auth.rbac import verify_complaint_access
from backend.app.services.report_service import (
    build_investigator_report_data, render_html_investigator_report
)


router = APIRouter(tags=["Investigator Reports"])


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


@router.get(
    "/complaints/{complaint_id}/report",
    response_model=InvestigatorReportDataResponse
)
def get_complaint_report_data(
    complaint_id: str,
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user)
):
    """
    Returns structured data for an investigator dossier scoped to the officer's jurisdiction.
    """
    complaint = _resolve_and_verify_complaint(complaint_id, current_user, db)
    return build_investigator_report_data(db, complaint.id, current_user)


@router.get(
    "/complaints/{complaint_id}/report/export"
)
def export_complaint_report(
    complaint_id: str,
    format: str = Query("html", pattern="^(html|json)$"),
    download: bool = Query(False),
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user)
):
    """
    Exports a scoped, print-ready HTML or JSON Investigator Dossier.
    """
    complaint = _resolve_and_verify_complaint(complaint_id, current_user, db)

    if format == "json":
        data = build_investigator_report_data(db, complaint.id, current_user)
        return data

    html_content = render_html_investigator_report(db, complaint.id, current_user)
    
    headers = {
        "X-Content-Type-Options": "nosniff",
        "Content-Security-Policy": "default-src 'self' 'unsafe-inline';"
    }
    if download:
        safe_name = f"dossier_{complaint.complaint_number}.html"
        headers["Content-Disposition"] = f'attachment; filename="{safe_name}"'

    return HTMLResponse(content=html_content, status_code=200, headers=headers)


@router.get(
    "/complaints/{complaint_id}/report/html",
    response_class=HTMLResponse
)
def get_complaint_report_html(
    complaint_id: str,
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user)
):
    """
    Direct HTML view endpoint for the investigator dossier.
    """
    complaint = _resolve_and_verify_complaint(complaint_id, current_user, db)
    html_content = render_html_investigator_report(db, complaint.id, current_user)
    return HTMLResponse(
        content=html_content,
        status_code=200,
        headers={"X-Content-Type-Options": "nosniff"}
    )
