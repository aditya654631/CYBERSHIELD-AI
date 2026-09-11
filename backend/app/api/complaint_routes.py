import re
from datetime import datetime
from typing import List, Optional
from fastapi import APIRouter, Depends, HTTPException, Query, Response
from sqlalchemy.orm import Session
from sqlalchemy import func
from backend.app.models.db import get_db
from backend.app.models.models import Complaint, Account, Transaction, ComplaintAccount, User, Prediction, Alert
from backend.app.schemas.schemas import ComplaintCreate, ComplaintResponse
from backend.app.auth.security import get_current_user
from backend.app.services.audit_service import log_audit
from backend.app.services.scenario_linking_service import (
    link_complaint_to_scenario,
    get_scenario_for_complaint,
    get_transactions_for_complaint
)
from backend.app.services.delhi_origin_resolver import resolve_delhi_origin

router = APIRouter(prefix="/complaints", tags=["Complaints"])

def generate_complaint_number(db: Session) -> str:
    """
    Generates a collision-safe operational complaint number using the CMP-NEW-XXXXXX namespace.
    Safely separated from legacy CMP-1042 and synthetic CMP-DL-0001..3000.
    """
    latest = db.query(Complaint.complaint_number).filter(
        Complaint.complaint_number.like("CMP-NEW-%")
    ).order_by(Complaint.id.desc()).first()

    next_seq = 1
    if latest and latest[0]:
        match = re.search(r"CMP-NEW-(\d+)", latest[0])
        if match:
            next_seq = int(match.group(1)) + 1

    comp_num = f"CMP-NEW-{next_seq:06d}"
    while db.query(Complaint.id).filter(Complaint.complaint_number == comp_num).first():
        next_seq += 1
        comp_num = f"CMP-NEW-{next_seq:06d}"

    return comp_num

def _enrich_complaint_response(db: Session, complaint: Complaint) -> Complaint:
    """Enriches a complaint model with direct and scenario linking metadata for API responses."""
    direct_txs = (
        db.query(Transaction)
        .filter(Transaction.complaint_id == complaint.id)
        .order_by(Transaction.timestamp.asc(), Transaction.id.asc())
        .all()
    )
    if direct_txs:
        complaint.source_scenario = None
        complaint.scenario_link_status = "DIRECT_OFFICER_INPUT"
        primary_tx = direct_txs[0]
        complaint.transaction_ref = primary_tx.transaction_ref
        complaint.transaction_time = primary_tx.timestamp
        if primary_tx.sender:
            complaint.victim_bank = primary_tx.sender.bank_name
        if primary_tx.receiver:
            complaint.beneficiary_bank = primary_tx.receiver.bank_name
            holder = primary_tx.receiver.holder_name
            if holder and holder.startswith("Beneficiary (") and holder.endswith(")"):
                complaint.beneficiary_id = holder[13:-1]
            else:
                complaint.beneficiary_id = primary_tx.receiver.masked_account or holder
    else:
        scenario = get_scenario_for_complaint(db, complaint)
        if scenario and scenario.id != complaint.id:
            complaint.source_scenario = scenario.complaint_number
            complaint.scenario_link_status = "LINKED"
        elif complaint.state and complaint.state.strip().lower() != "delhi":
            complaint.source_scenario = None
            complaint.scenario_link_status = "SCENARIO_UNAVAILABLE"
        else:
            complaint.source_scenario = None
            complaint.scenario_link_status = "NOT_LINKED"

    # Derive prediction_status authoritative from PostgreSQL Prediction table
    pred_exists = db.query(Prediction.id).filter(Prediction.complaint_id == complaint.id).first()
    if pred_exists:
        complaint.prediction_status = "AVAILABLE"
    else:
        complaint.prediction_status = "NOT RUN"

    # Derive alert_status authoritative from PostgreSQL Alert table
    alerts = db.query(Alert.status).filter(Alert.complaint_id == complaint.id).all()
    if alerts:
        if any(a[0] == "ACKNOWLEDGED" for a in alerts):
            complaint.alert_status = "ACKNOWLEDGED"
        else:
            complaint.alert_status = "GENERATED"
    else:
        complaint.alert_status = "NOT GENERATED"

    complaint.locality = getattr(complaint, "locality", None) or complaint.victim_location
    complaint.provenance_mode = getattr(complaint, "provenance_mode", None) or (
        "DIRECT_OFFICER_INPUT" if direct_txs else "LINKED_SYNTHETIC_SCENARIO"
    )
    complaint.linked_account_count = len(complaint.accounts)
    complaint.available_transaction_count = len(get_transactions_for_complaint(db, complaint))
    return complaint

def _batch_enrich_complaints(db: Session, complaints: List[Complaint]) -> List[Complaint]:
    """Optimized batch enrichment for complaint listings."""
    if not complaints:
        return complaints
    comp_ids = [c.id for c in complaints]

    pred_comp_ids = set(
        r[0] for r in db.query(Prediction.complaint_id).filter(Prediction.complaint_id.in_(comp_ids)).all()
    )

    alert_rows = db.query(Alert.complaint_id, Alert.status).filter(Alert.complaint_id.in_(comp_ids)).all()
    alert_map = {}
    for cid, st in alert_rows:
        alert_map.setdefault(cid, []).append(st)

    for c in complaints:
        _enrich_complaint_response(db, c)

        if c.id in pred_comp_ids:
            c.prediction_status = "AVAILABLE"
        else:
            c.prediction_status = "NOT RUN"

        c_alerts = alert_map.get(c.id, [])
        if c_alerts:
            if "ACKNOWLEDGED" in c_alerts:
                c.alert_status = "ACKNOWLEDGED"
            else:
                c.alert_status = "GENERATED"
        else:
            c.alert_status = "NOT GENERATED"

    return complaints

@router.get("", response_model=List[ComplaintResponse])
def list_complaints(
    response: Response,
    fraud_type: Optional[str] = None,
    risk_level: Optional[str] = None,
    case_status: Optional[str] = None,
    district: Optional[str] = None,
    prediction_status: Optional[str] = None,
    alert_status: Optional[str] = None,
    search: Optional[str] = None,
    limit: int = 25,
    skip: int = 0,
    page: Optional[int] = None,
    state: Optional[str] = "Delhi",
    db: Session = Depends(get_db)
):
    query = db.query(Complaint)

    # Section 3: Delhi Operational Pilot Scope (Strictly Delhi, exclude outside historical rows)
    if state and state.upper() != "ALL":
        query = query.filter(
            func.lower(Complaint.state) == state.lower(),
            ~Complaint.complaint_number.like("CMP-OUTSIDE-%"),
            ~Complaint.victim_location.ilike("%Madhya Pradesh%"),
            ~Complaint.victim_location.ilike("%Bhopal%"),
            ~Complaint.victim_location.ilike("%Indore%")
        )

    # Operational Filters
    if fraud_type and fraud_type != "ALL":
        query = query.filter(Complaint.fraud_type.ilike(f"%{fraud_type}%"))
    if risk_level and risk_level != "ALL":
        query = query.filter(Complaint.risk_level == risk_level)
    if case_status and case_status != "ALL":
        norm_status = case_status.replace(" ", "_").upper()
        query = query.filter(
            (func.upper(Complaint.case_status) == norm_status) |
            (func.upper(Complaint.case_status) == case_status.upper())
        )
    if district and district != "ALL":
        query = query.filter(Complaint.district.ilike(f"%{district}%"))

    # Authoritative DB Prediction filter
    if prediction_status and prediction_status != "ALL":
        pred_subq = db.query(Prediction.complaint_id).distinct().scalar_subquery()
        if prediction_status.upper() in ("AVAILABLE", "COMPLETED"):
            query = query.filter(Complaint.id.in_(pred_subq))
        elif prediction_status.upper() in ("NOT RUN", "NOT_RUN", "PENDING"):
            query = query.filter(~Complaint.id.in_(pred_subq))

    # Authoritative DB Alert filter
    if alert_status and alert_status != "ALL":
        if alert_status.upper() == "ACKNOWLEDGED":
            ack_subq = db.query(Alert.complaint_id).filter(Alert.status == "ACKNOWLEDGED").distinct().scalar_subquery()
            query = query.filter(Complaint.id.in_(ack_subq))
        elif alert_status.upper() == "GENERATED":
            gen_subq = db.query(Alert.complaint_id).filter(Alert.status != "ACKNOWLEDGED").distinct().scalar_subquery()
            query = query.filter(Complaint.id.in_(gen_subq))
        elif alert_status.upper() in ("NOT GENERATED", "NOT_GENERATED"):
            any_alert_subq = db.query(Alert.complaint_id).distinct().scalar_subquery()
            query = query.filter(~Complaint.id.in_(any_alert_subq))

    # Search: Complaint number, victim name, locality, victim location, fraud type, or transaction ref
    if search:
        s = search.strip()
        if s:
            tx_subq = db.query(Transaction.complaint_id).filter(Transaction.transaction_ref.ilike(f"%{s}%")).scalar_subquery()
            query = query.filter(
                (Complaint.complaint_number.ilike(f"%{s}%")) |
                (Complaint.victim_name.ilike(f"%{s}%")) |
                (Complaint.locality.ilike(f"%{s}%")) |
                (Complaint.victim_location.ilike(f"%{s}%")) |
                (Complaint.fraud_type.ilike(f"%{s}%")) |
                Complaint.id.in_(tx_subq)
            )

    # Calculate total matching count before pagination
    total_count = query.count()

    # Pagination calculation
    eff_page = page if page and page > 0 else (skip // limit + 1 if limit > 0 else 1)
    eff_skip = (eff_page - 1) * limit if page and page > 0 else skip
    total_pages = max(1, (total_count + limit - 1) // limit) if limit > 0 else 1

    # Attach pagination headers
    response.headers["X-Total-Count"] = str(total_count)
    response.headers["X-Page"] = str(eff_page)
    response.headers["X-Limit"] = str(limit)
    response.headers["X-Total-Pages"] = str(total_pages)

    # Natural chronological ordering by reported_at DESC, id DESC
    complaints = query.order_by(
        Complaint.reported_at.desc(),
        Complaint.id.desc()
    ).offset(eff_skip).limit(limit).all()

    return _batch_enrich_complaints(db, complaints)

@router.post("", response_model=ComplaintResponse)
def create_complaint(
    data: ComplaintCreate,
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user)
):
    # Section 22: Duplicate / Idempotency Check on transaction reference
    if data.transaction_ref and data.transaction_ref.strip():
        existing_tx = db.query(Transaction).filter(Transaction.transaction_ref == data.transaction_ref.strip()).first()
        if existing_tx and existing_tx.complaint_id:
            existing_comp = db.query(Complaint).filter(Complaint.id == existing_tx.complaint_id).first()
            if existing_comp:
                return _enrich_complaint_response(db, existing_comp)

    comp_num = generate_complaint_number(db)

    reported_time = data.reported_at or datetime.utcnow()
    incident_time = data.incident_time or reported_time
    victim_state = data.state or "Delhi"
    locality = data.locality or "Connaught Place"

    # Deterministic Delhi Origin Resolution (Priority: Coords -> Cluster -> Alias -> District -> Unresolved)
    origin_res = resolve_delhi_origin(
        locality=data.locality,
        district=data.district,
        lat=data.victim_lat,
        lon=data.victim_lon
    )
    victim_district = data.district or origin_res["resolved_district"] or "CENTRAL_NEW_DELHI"
    victim_lat = data.victim_lat
    victim_lon = data.victim_lon
    victim_location = data.victim_location or f"{locality}, {victim_district}, {victim_state}"

    # Atomic Registration Block (Rollback on any step failure)
    try:
        # Initial pre-prediction evaluation state: zero fake risk, zero fake prediction
        complaint = Complaint(
            complaint_number=comp_num,
            fraud_type=data.fraud_type,
            amount=data.amount,
            victim_name=data.victim_name or "Anonymous Victim",
            victim_phone=data.victim_phone or "+91 98765 43210",
            victim_location=victim_location,
            locality=locality,
            state=victim_state,
            district=victim_district,
            payment_channel=data.payment_channel,
            reported_at=reported_time,
            incident_time=incident_time,
            victim_lat=victim_lat,
            victim_lon=victim_lon,
            description=data.description,
            provenance_mode="DIRECT_OFFICER_INPUT",
            risk_level="PENDING_EVALUATION",
            risk_score=None,
            prediction_status="NOT RUN",
            case_status="ACTIVE"
        )
        db.add(complaint)
        db.flush()

        # Direct Officer Transaction Persistence:
        # If officer supplied real transaction / bank / beneficiary data, persist as direct complaint context
        has_direct_tx = bool(
            data.transaction_ref or data.victim_bank or data.beneficiary_bank or data.beneficiary_id
        )
        if has_direct_tx:
            # 1. Victim Account
            v_bank = data.victim_bank or "State Bank of India"
            v_acc_no = f"ACC-VIC-{complaint.id:06d}"
            v_acc = db.query(Account).filter(Account.account_number == v_acc_no).first()
            if not v_acc:
                v_acc = Account(
                    account_number=v_acc_no,
                    masked_account=f"XXXX-XXXX-{complaint.id:04d}",
                    bank_name=v_bank,
                    holder_name=data.victim_name or "Complainant Victim",
                    account_type="SAVINGS",
                    state=victim_state,
                    district=victim_district,
                    is_mule=False
                )
                db.add(v_acc)
                db.flush()

            ca_v = ComplaintAccount(
                complaint_id=complaint.id,
                account_id=v_acc.id,
                association_type="VICTIM"
            )
            db.add(ca_v)

            # 2. Beneficiary Account
            b_bank = data.beneficiary_bank or "HDFC Bank"
            raw_ben = data.beneficiary_account_number or data.beneficiary_id or f"BEN-{complaint.id:06d}"
            b_acc_no = f"ACC-BEN-{complaint.id:06d}" if not data.beneficiary_account_number else data.beneficiary_account_number
            b_acc = db.query(Account).filter(Account.account_number == b_acc_no).first()
            if not b_acc:
                masked_b = f"XXXX-{raw_ben[-4:]}" if len(raw_ben) >= 4 else f"XXXX-{raw_ben}"
                b_acc = Account(
                    account_number=b_acc_no,
                    masked_account=masked_b,
                    bank_name=b_bank,
                    branch=data.beneficiary_upi_id or "Digital Clearing Branch",
                    ifsc=data.ifsc_code or "HDFC0001234",
                    holder_name=f"Beneficiary ({raw_ben})",
                    account_type="CURRENT" if "CURRENT" in (data.payment_channel or "").upper() else "SAVINGS",
                    state=victim_state,
                    district=victim_district,
                    is_mule=False,
                    flag_reason=None
                )
                db.add(b_acc)
                db.flush()

            ca_b = ComplaintAccount(
                complaint_id=complaint.id,
                account_id=b_acc.id,
                association_type="BENEFICIARY"
            )
            db.add(ca_b)

            # 3. Direct Transaction
            tx_ref = data.transaction_ref or f"UTR-{complaint.complaint_number}-01"
            existing_tx = db.query(Transaction).filter(Transaction.transaction_ref == tx_ref).first()
            if existing_tx:
                tx_ref = f"{tx_ref}-{complaint.id}"
            tx_time = data.transaction_time or incident_time
            direct_tx = Transaction(
                transaction_ref=tx_ref,
                complaint_id=complaint.id,
                sender_account_id=v_acc.id,
                receiver_account_id=b_acc.id,
                amount=data.amount,
                payment_channel=data.payment_channel,
                timestamp=tx_time,
                hop_number=1,
                status="COMPLETED",
                suspicious_flag=True
            )
            db.add(direct_tx)
            db.flush()

        # Link complaint to scenario (preserves direct data if present)
        link_result = link_complaint_to_scenario(db, complaint)
        db.commit()
        db.refresh(complaint)
    except Exception as exc:
        db.rollback()
        raise HTTPException(status_code=500, detail=f"Atomic complaint registration failed: {str(exc)}")

    _enrich_complaint_response(db, complaint)

    # Log audit trail with authoritative authenticated officer
    log_audit(
        db=db,
        user_id=current_user.id,
        officer_name=current_user.full_name,
        role=current_user.role,
        action="COMPLAINT_CREATED",
        case_number=comp_num,
        details=f"New complaint registered: {comp_num} for ₹{data.amount:,.2f} by {current_user.full_name} [Scenario Status: {link_result.get('status')}]"
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

    _enrich_complaint_response(db, complaint)
    return complaint
