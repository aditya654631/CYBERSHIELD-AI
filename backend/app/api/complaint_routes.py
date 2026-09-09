import random
from datetime import datetime
from typing import List, Optional
from fastapi import APIRouter, Depends, HTTPException, Query
from sqlalchemy.orm import Session
from backend.app.models.db import get_db
from backend.app.models.models import Complaint, Account, Transaction
from backend.app.schemas.schemas import ComplaintCreate, ComplaintResponse
from backend.app.services.audit_service import log_audit

router = APIRouter(prefix="/complaints", tags=["Complaints"])

@router.get("", response_model=List[ComplaintResponse])
def list_complaints(
    fraud_type: Optional[str] = None,
    risk_level: Optional[str] = None,
    search: Optional[str] = None,
    limit: int = 100,
    skip: int = 0,
    db: Session = Depends(get_db)
):
    query = db.query(Complaint)
    if fraud_type and fraud_type != "ALL":
        query = query.filter(Complaint.fraud_type.ilike(f"%{fraud_type}%"))
    if risk_level and risk_level != "ALL":
        query = query.filter(Complaint.risk_level == risk_level)
    if search:
        query = query.filter(
            (Complaint.complaint_number.ilike(f"%{search}%")) |
            (Complaint.victim_location.ilike(f"%{search}%")) |
            (Complaint.fraud_type.ilike(f"%{search}%"))
        )

    # Ensure CMP-1042 is at top if present
    complaints = query.order_by(
        (Complaint.complaint_number == "CMP-1042").desc(),
        Complaint.reported_at.desc()
    ).offset(skip).limit(limit).all()

    return complaints

@router.post("", response_model=ComplaintResponse)
def create_complaint(data: ComplaintCreate, db: Session = Depends(get_db)):
    # Generate unique complaint number
    count = db.query(Complaint).count() + 1050
    comp_num = f"CMP-{count}"

    # Determine initial risk heuristic
    risk_score = 0.85 if data.amount > 100000 else (0.65 if data.amount > 40000 else 0.45)
    risk_level = "CRITICAL" if risk_score >= 0.80 else ("HIGH" if risk_score >= 0.60 else "MEDIUM")

    complaint = Complaint(
        complaint_number=comp_num,
        fraud_type=data.fraud_type,
        amount=data.amount,
        victim_name=data.victim_name,
        victim_phone=data.victim_phone,
        victim_location=data.victim_location,
        state=data.state,
        district=data.district,
        payment_channel=data.payment_channel,
        reported_at=datetime.utcnow(),
        incident_time=datetime.utcnow(),
        risk_level=risk_level,
        risk_score=risk_score,
        prediction_status="PENDING",
        case_status="ACTIVE"
    )
    db.add(complaint)
    db.flush()

    # Create synthetic victim and destination account to give immediate graph intelligence
    victim_acc = Account(
        account_number=f"99{random.randint(10000000, 99999999)}",
        masked_account=f"ACC••••{random.randint(1000, 9999)}",
        bank_name="State Bank of India",
        branch=f"{data.district} Main Branch",
        holder_name=data.victim_name or "Victim Account",
        risk_score=0.05,
        is_mule=False
    )
    mule_acc = Account(
        account_number=f"77{random.randint(10000000, 99999999)}",
        masked_account=f"ACC••••{random.randint(1000, 9999)}",
        bank_name="HDFC Bank",
        branch="Layering Node",
        holder_name="Suspect Intermediary",
        risk_score=0.82,
        is_mule=True,
        flag_reason="Rapid fund layering"
    )
    db.add_all([victim_acc, mule_acc])
    db.flush()

    tx = Transaction(
        transaction_ref=f"TXN-IN-{random.randint(1000000, 9999999)}",
        complaint_id=complaint.id,
        sender_account_id=victim_acc.id,
        receiver_account_id=mule_acc.id,
        amount=data.amount,
        payment_channel=data.payment_channel,
        timestamp=datetime.utcnow(),
        hop_number=1,
        status="COMPLETED",
        suspicious_flag=True
    )
    db.add(tx)

    db.commit()
    db.refresh(complaint)

    # Log audit
    log_audit(
        db=db,
        officer_name="LEA Duty Officer",
        role="DISTRICT_LEA",
        action="COMPLAINT_CREATED",
        case_number=comp_num,
        details=f"New complaint registered: {comp_num} for ₹{data.amount:,.2f}"
    )

    return complaint

@router.get("/{id}", response_model=ComplaintResponse)
def get_complaint(id: str, db: Session = Depends(get_db)):
    if id.isdigit():
        complaint = db.query(Complaint).filter(Complaint.id == int(id)).first()
    else:
        complaint = db.query(Complaint).filter(Complaint.complaint_number == id).first()

    if not complaint:
        raise HTTPException(status_code=404, detail="Complaint not found")

    # Log audit
    log_audit(
        db=db,
        officer_name="Inspector R. Verma",
        role="STATE_LEA",
        action="CASE_VIEWED",
        case_number=complaint.complaint_number,
        details=f"Case file accessed for {complaint.complaint_number}"
    )

    return complaint
