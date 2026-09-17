import re
from datetime import datetime, timedelta
from typing import List, Optional
from fastapi import APIRouter, Depends, HTTPException, Query, Response
from sqlalchemy.orm import Session, joinedload
from sqlalchemy import func
from backend.app.models.db import get_db
from backend.app.models.models import Complaint, Account, Transaction, ComplaintAccount, User, Prediction, Alert, Withdrawal, ATMLocation
from backend.app.schemas.schemas import ComplaintCreate, ComplaintResponse, GraphDataResponse
from backend.app.services.graph_service import build_complaint_graph
from backend.app.auth.security import get_current_user
from backend.app.auth.rbac import (
    require_roles,
    verify_complaint_access,
    filter_complaints_by_jurisdiction,
    RoleEnum
)
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
    complaint.provenance_mode = (
        getattr(complaint, "provenance_mode", None)
        if getattr(complaint, "provenance_mode", None) in ("CONTROLLED_SYNTHETIC_DEMO", "SYNTHETIC_DEMO")
        else "SYNTHETIC_DEMO" if complaint.complaint_number.startswith("CMP-DL-")
        else "LINKED_SYNTHETIC_SCENARIO" if complaint.scenario_link_status == "LINKED"
        else "DIRECT_OFFICER_INPUT"
    )
    complaint.linked_account_count = len(complaint.accounts)
    complaint.available_transaction_count = len(get_transactions_for_complaint(db, complaint))
    return complaint

def _batch_enrich_complaints(db: Session, complaints: List[Complaint]) -> List[Complaint]:
    """Optimized batch enrichment for complaint listings without N+1 queries."""
    if not complaints:
        return complaints
    comp_ids = [c.id for c in complaints]

    # Batch 1: Predictions existence
    pred_comp_ids = set(
        r[0] for r in db.query(Prediction.complaint_id).filter(Prediction.complaint_id.in_(comp_ids)).all()
    )

    # Batch 2: Alerts status
    alert_rows = db.query(Alert.complaint_id, Alert.status).filter(Alert.complaint_id.in_(comp_ids)).all()
    alert_map = {}
    for cid, st in alert_rows:
        alert_map.setdefault(cid, []).append(st)

    # Batch 3: Account counts
    acct_counts = dict(
        db.query(ComplaintAccount.complaint_id, func.count(ComplaintAccount.id))
        .filter(ComplaintAccount.complaint_id.in_(comp_ids))
        .group_by(ComplaintAccount.complaint_id)
        .all()
    )

    # Batch 4: Direct transactions with sender/receiver preloaded
    direct_tx_rows = (
        db.query(Transaction)
        .options(joinedload(Transaction.sender), joinedload(Transaction.receiver))
        .filter(Transaction.complaint_id.in_(comp_ids))
        .order_by(Transaction.timestamp.asc(), Transaction.id.asc())
        .all()
    )
    direct_tx_map = {}
    for tx in direct_tx_rows:
        direct_tx_map.setdefault(tx.complaint_id, []).append(tx)

    for c in complaints:
        c_txs = direct_tx_map.get(c.id, [])
        if c_txs:
            c.source_scenario = None
            c.scenario_link_status = "DIRECT_OFFICER_INPUT"
            c.available_transaction_count = len(c_txs)
            primary_tx = c_txs[0]
            c.transaction_ref = primary_tx.transaction_ref
            c.transaction_time = primary_tx.timestamp
            if primary_tx.sender:
                c.victim_bank = primary_tx.sender.bank_name
            if primary_tx.receiver:
                c.beneficiary_bank = primary_tx.receiver.bank_name
                holder = primary_tx.receiver.holder_name
                if holder and holder.startswith("Beneficiary (") and holder.endswith(")"):
                    c.beneficiary_id = holder[13:-1]
                else:
                    c.beneficiary_id = primary_tx.receiver.masked_account or holder
        else:
            c.source_scenario = None
            c.scenario_link_status = "NOT_LINKED"
            c.available_transaction_count = 0

        c.prediction_status = "AVAILABLE" if c.id in pred_comp_ids else "NOT RUN"

        c_alerts = alert_map.get(c.id, [])
        if c_alerts:
            if "ACKNOWLEDGED" in c_alerts:
                c.alert_status = "ACKNOWLEDGED"
            else:
                c.alert_status = "GENERATED"
        else:
            c.alert_status = "NOT GENERATED"

        c.locality = getattr(c, "locality", None) or c.victim_location
        c.provenance_mode = (
            getattr(c, "provenance_mode", None)
            if getattr(c, "provenance_mode", None) in ("CONTROLLED_SYNTHETIC_DEMO", "SYNTHETIC_DEMO")
            else "SYNTHETIC_DEMO" if c.complaint_number.startswith("CMP-DL-")
            else "LINKED_SYNTHETIC_SCENARIO" if c.scenario_link_status == "LINKED"
            else "DIRECT_OFFICER_INPUT"
        )
        c.linked_account_count = acct_counts.get(c.id, 0)

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
    state: Optional[str] = None,
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user)
):
    query = db.query(Complaint)

    # Centralized Jurisdiction Filtering
    query = filter_complaints_by_jurisdiction(query, current_user, db)

    # If I4C_ADMIN optionally filters by state
    if current_user.role == RoleEnum.I4C_ADMIN and state and state.upper() != "ALL":
        query = query.filter(func.lower(Complaint.state) == state.lower())

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

def _generate_synthetic_multihop_trail(
    db: Session,
    complaint: Complaint,
    data: ComplaintCreate,
    victim_state: str,
    victim_district: str,
    incident_time: datetime,
    reported_time: datetime
):
    """
    Persists a realistic, deterministic, duplicate-safe 3-hop transaction trail in PostgreSQL
    strictly for controlled synthetic demo complaints.
    
    Generates:
      - 6 Accounts: Victim, Primary Beneficiary, Intermediary A, Intermediary B, Downstream C, Downstream D
      - 6 ComplaintAccount records
      - 5 Transactions with conserved amounts and strictly causal timestamps
      - 2 Terminal ATM Cash-Out Withdrawals pointing to real existing ATMLocation rows in Delhi
    """
    cid = complaint.id
    amt = float(complaint.amount)

    # 1. Accounts
    # 1.1 Victim Account
    v_acc_no = f"ACC-SYN-VIC-{cid:06d}"
    v_acc = db.query(Account).filter(Account.account_number == v_acc_no).first()
    if not v_acc:
        v_acc = Account(
            account_number=v_acc_no,
            masked_account=f"ACC••••{1000 + (cid % 900):04d}",
            bank_name=data.victim_bank or "State Bank of India",
            branch="New Delhi Main Branch",
            ifsc="SBIN0000691",
            holder_name=data.victim_name or "Complainant Victim",
            account_type="SAVINGS",
            state=victim_state,
            district=victim_district,
            risk_score=0.05,
            is_mule=False
        )
        db.add(v_acc)
        db.flush()

    # 1.2 Primary Beneficiary Account
    raw_ben = data.beneficiary_id or data.beneficiary_account_number or data.beneficiary_upi_id or "Layer 1 Primary"
    b_acc_no = data.beneficiary_account_number or f"ACC-SYN-BEN-{cid:06d}"
    b_acc = db.query(Account).filter(Account.account_number == b_acc_no).first()
    if not b_acc:
        b_acc = Account(
            account_number=b_acc_no,
            masked_account=f"ACC••••{2000 + (cid % 900):04d}",
            bank_name=data.beneficiary_bank or "HDFC Bank",
            branch="Connaught Place Branch",
            ifsc=data.ifsc_code or "HDFC0000003",
            holder_name=f"Primary Beneficiary ({raw_ben})",
            account_type="SAVINGS",
            state="Delhi",
            district=victim_district,
            risk_score=0.65,
            is_mule=False,
            flag_reason="Rapid multi-channel pass-through recipient"
        )
        db.add(b_acc)
        db.flush()

    # 1.3 Intermediary Account A
    int_a_no = f"ACC-SYN-INTA-{cid:06d}"
    int_a = db.query(Account).filter(Account.account_number == int_a_no).first()
    if not int_a:
        int_a = Account(
            account_number=int_a_no,
            masked_account=f"ACC••••{3000 + (cid % 900):04d}",
            bank_name="Axis Bank",
            branch="Barakhamba Road Branch",
            ifsc="UTIB0000015",
            holder_name="Intermediary Flow Account A",
            account_type="CURRENT",
            state="Delhi",
            district="CENTRAL_NEW_DELHI",
            risk_score=0.76,
            is_mule=False,
            flag_reason="High-velocity intermediary aggregator account"
        )
        db.add(int_a)
        db.flush()

    # 1.4 Intermediary Account B
    int_b_no = f"ACC-SYN-INTB-{cid:06d}"
    int_b = db.query(Account).filter(Account.account_number == int_b_no).first()
    if not int_b:
        int_b = Account(
            account_number=int_b_no,
            masked_account=f"ACC••••{4000 + (cid % 900):04d}",
            bank_name="ICICI Bank",
            branch="Paharganj Branch",
            ifsc="ICIC0000007",
            holder_name="Intermediary Flow Account B",
            account_type="CURRENT",
            state="Delhi",
            district="CENTRAL_NEW_DELHI",
            risk_score=0.72,
            is_mule=False,
            flag_reason="Convergent layering intermediary account"
        )
        db.add(int_b)
        db.flush()

    # 1.5 Downstream Account C (Heuristic flagged mule candidate: risk_score 0.82 >= 0.70)
    dwn_c_no = f"ACC-SYN-DWNC-{cid:06d}"
    dwn_c = db.query(Account).filter(Account.account_number == dwn_c_no).first()
    if not dwn_c:
        dwn_c = Account(
            account_number=dwn_c_no,
            masked_account=f"ACC••••{5000 + (cid % 900):04d}",
            bank_name="Kotak Mahindra Bank",
            branch="Rajendra Place Branch",
            ifsc="KKBK0000180",
            holder_name="Downstream Account C",
            account_type="SAVINGS",
            state="Delhi",
            district="CENTRAL_NEW_DELHI",
            risk_score=0.82,
            is_mule=True,
            flag_reason="Rapid terminal pass-through to ATM withdrawal"
        )
        db.add(dwn_c)
        db.flush()

    # 1.6 Downstream Account D (Heuristic flagged mule candidate: risk_score 0.78 >= 0.70)
    dwn_d_no = f"ACC-SYN-DWND-{cid:06d}"
    dwn_d = db.query(Account).filter(Account.account_number == dwn_d_no).first()
    if not dwn_d:
        dwn_d = Account(
            account_number=dwn_d_no,
            masked_account=f"ACC••••{6000 + (cid % 900):04d}",
            bank_name="Punjab National Bank",
            branch="Karol Bagh Branch",
            ifsc="PUNB0000100",
            holder_name="Downstream Account D",
            account_type="SAVINGS",
            state="Delhi",
            district="CENTRAL_NEW_DELHI",
            risk_score=0.78,
            is_mule=True,
            flag_reason="Terminal ATM disbursement feeder account"
        )
        db.add(dwn_d)
        db.flush()

    # 2. Link all 6 accounts in ComplaintAccount
    account_roles = [
        (v_acc.id, "VICTIM"),
        (b_acc.id, "BENEFICIARY"),
        (int_a.id, "INTERMEDIARY"),
        (int_b.id, "INTERMEDIARY"),
        (dwn_c.id, "SUSPECT"),
        (dwn_d.id, "SUSPECT")
    ]
    for acc_id, role in account_roles:
        existing_ca = db.query(ComplaintAccount).filter(
            ComplaintAccount.complaint_id == cid,
            ComplaintAccount.account_id == acc_id
        ).first()
        if not existing_ca:
            db.add(ComplaintAccount(
                complaint_id=cid,
                account_id=acc_id,
                association_type=role
            ))
    db.flush()

    # 3. Conserved Amounts Calculation
    amt_1 = round(amt * 0.58, 2)
    amt_2 = round(amt * 0.38, 2)
    amt_3 = round(amt_1 * 0.85, 2)
    amt_4 = round(amt_2 * 0.85, 2)
    wdl_1_amt = round(amt_3 * 0.75, 2)
    wdl_2_amt = round(amt_4 * 0.75, 2)

    # 4. Strictly Causal Timestamps
    r_time = reported_time or datetime.utcnow()
    i_time = incident_time or r_time
    if i_time > r_time - timedelta(minutes=75):
        base_t = r_time - timedelta(minutes=75)
    else:
        base_t = i_time

    t1 = base_t
    t2 = t1 + timedelta(minutes=8)
    t3 = t1 + timedelta(minutes=14)
    t4 = t2 + timedelta(minutes=10)
    t5 = t3 + timedelta(minutes=12)
    w1_time = t4 + timedelta(minutes=15)
    w2_time = t5 + timedelta(minutes=18)

    # 5. 5 Multi-Hop Transactions (Max Hop Depth = 3)
    tx_definitions = [
        (data.transaction_ref or f"UTR-DL-DEMO-{cid:06d}-01", v_acc.id, b_acc.id, amt, data.payment_channel or "UPI", t1, 1),
        (f"UTR-DL-DEMO-{cid:06d}-02", b_acc.id, int_a.id, amt_1, "IMPS", t2, 2),
        (f"UTR-DL-DEMO-{cid:06d}-03", b_acc.id, int_b.id, amt_2, "NEFT", t3, 2),
        (f"UTR-DL-DEMO-{cid:06d}-04", int_a.id, dwn_c.id, amt_3, "IMPS", t4, 3),
        (f"UTR-DL-DEMO-{cid:06d}-05", int_b.id, dwn_d.id, amt_4, "RTGS", t5, 3),
    ]

    for ref, s_id, r_id, t_amt, ch, ts, hop in tx_definitions:
        existing_tx = db.query(Transaction).filter(Transaction.transaction_ref == ref).first()
        if not existing_tx:
            db.add(Transaction(
                transaction_ref=ref,
                complaint_id=cid,
                sender_account_id=s_id,
                receiver_account_id=r_id,
                amount=t_amt,
                payment_channel=ch,
                timestamp=ts,
                hop_number=hop,
                status="COMPLETED",
                suspicious_flag=True
            ))
    db.flush()

    # 6. Resolve 2 Real Existing Delhi ATMLocation rows from PostgreSQL
    delhi_atms = (
        db.query(ATMLocation)
        .filter(
            (func.lower(ATMLocation.state) == "delhi") |
            (ATMLocation.district.ilike("%delhi%"))
        )
        .order_by(ATMLocation.id.asc())
        .limit(5)
        .all()
    )
    if len(delhi_atms) < 2:
        delhi_atms = db.query(ATMLocation).order_by(ATMLocation.id.asc()).limit(5).all()

    if len(delhi_atms) < 2:
        raise HTTPException(
            status_code=500,
            detail="Insufficient ATMLocation records found in PostgreSQL. Controlled demo trace requires at least 2 real ATM records."
        )

    atm_1 = delhi_atms[0]
    atm_2 = delhi_atms[1]

    # 7. 2 Terminal Cash-Out Withdrawals
    existing_w1 = db.query(Withdrawal).filter(Withdrawal.account_id == dwn_c.id).first()
    if not existing_w1:
        db.add(Withdrawal(
            atm_id=atm_1.id,
            account_id=dwn_c.id,
            amount=wdl_1_amt,
            timestamp=w1_time,
            success=True,
            camera_flagged=True
        ))

    existing_w2 = db.query(Withdrawal).filter(Withdrawal.account_id == dwn_d.id).first()
    if not existing_w2:
        db.add(Withdrawal(
            atm_id=atm_2.id,
            account_id=dwn_d.id,
            amount=wdl_2_amt,
            timestamp=w2_time,
            success=True,
            camera_flagged=False
        ))
    db.flush()

@router.post("", response_model=ComplaintResponse)
def create_complaint(
    data: ComplaintCreate,
    db: Session = Depends(get_db),
    current_user: User = Depends(require_roles(RoleEnum.I4C_ADMIN, RoleEnum.STATE_LEA, RoleEnum.DISTRICT_LEA))
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

    # Untrusted request body protection: Non-I4C officers cannot spoof their state/district
    if current_user.role == RoleEnum.STATE_LEA:
        victim_state = current_user.organization.state if current_user.organization else "Delhi"
    elif current_user.role == RoleEnum.DISTRICT_LEA:
        victim_state = current_user.organization.state if current_user.organization else "Delhi"
        data.district = current_user.organization.district if current_user.organization else data.district
    else:
        victim_state = data.state or "Delhi"

    locality = data.locality or data.victim_location or None

    # Deterministic Delhi Origin Resolution (Priority: Coords -> Cluster -> Alias -> District -> Unresolved)
    origin_res = resolve_delhi_origin(
        locality=locality,
        district=data.district,
        lat=data.victim_lat,
        lon=data.victim_lon
    )
    is_delhi = victim_state.strip().lower() == "delhi"
    if is_delhi:
        victim_state = "Delhi"
    victim_district = (
        data.district or origin_res["resolved_district"] or "UNRESOLVED"
    ) if is_delhi else (data.district or "UNRESOLVED")
    victim_lat = data.victim_lat
    victim_lon = data.victim_lon
    victim_location = data.victim_location or ", ".join(
        part for part in (locality, data.district or origin_res["resolved_district"] if is_delhi else data.district, victim_state) if part
    )

    # User Mandatory Rule: Explicit demo_mode: true ONLY triggers controlled synthetic expansion.
    is_demo = bool(data.demo_mode is True)
    assigned_provenance = "CONTROLLED_SYNTHETIC_DEMO" if is_demo else "DIRECT_OFFICER_INPUT"

    # Atomic Registration Block (Rollback on any step failure)
    try:
        # Initial pre-prediction evaluation state: zero fake risk, zero fake prediction
        complaint = Complaint(
            complaint_number=comp_num,
            fraud_type=data.fraud_type,
            amount=data.amount,
            victim_name=data.victim_name or "Anonymous Victim",
            victim_phone=data.victim_phone or None,
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
            provenance_mode=assigned_provenance,
            risk_level="PENDING_EVALUATION",
            risk_score=None,
            prediction_status="NOT RUN",
            case_status="ACTIVE"
        )
        db.add(complaint)
        db.flush()

        if is_demo:
            _generate_synthetic_multihop_trail(
                db=db,
                complaint=complaint,
                data=data,
                victim_state=victim_state,
                victim_district=victim_district,
                incident_time=incident_time,
                reported_time=reported_time
            )
            link_result = {"status": "CONTROLLED_SYNTHETIC_DEMO"}
        else:
            # Direct Officer Transaction Persistence:
            # Genuine officer input must remain evidence-faithful: 2 nodes / 1 transaction if that is all the officer supplied
            has_direct_tx = bool(
                data.transaction_ref or data.victim_bank or data.beneficiary_bank or data.beneficiary_id
                or data.beneficiary_account_number or data.beneficiary_upi_id or data.ifsc_code
            )
            if has_direct_tx:
                # 1. Victim Account
                v_bank = data.victim_bank or "Not provided"
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
                b_bank = data.beneficiary_bank or "Not provided"
                raw_ben = data.beneficiary_account_number or data.beneficiary_id or data.beneficiary_upi_id or "Not provided"
                b_acc_no = f"ACC-BEN-{complaint.id:06d}" if not data.beneficiary_account_number else data.beneficiary_account_number
                b_acc = db.query(Account).filter(Account.account_number == b_acc_no).first()
                if not b_acc:
                    masked_b = f"XXXX-{raw_ben[-4:]}" if len(raw_ben) >= 4 else f"XXXX-{raw_ben}"
                    b_acc = Account(
                        account_number=b_acc_no,
                        masked_account=masked_b,
                        bank_name=b_bank,
                        branch=data.beneficiary_upi_id or None,
                        ifsc=data.ifsc_code or None,
                        holder_name=f"Beneficiary ({raw_ben})",
                        account_type="CURRENT" if "CURRENT" in (data.payment_channel or "").upper() else "SAVINGS",
                        # A victim's location is not evidence of beneficiary geography.
                        state="UNKNOWN",
                        district=None,
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

            # A newly registered complaint remains grounded in the officer's
            # submitted evidence. Historical scenarios are only used when an
            # explicit, persisted scenario link already exists.
            link_result = {"status": "DIRECT_OFFICER_INPUT"}
        db.commit()
        db.refresh(complaint)
    except Exception as exc:
        db.rollback()
        raise HTTPException(status_code=500, detail="Complaint registration failed; no partial complaint was saved.") from exc

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
def get_complaint(
    id: str,
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user)
):
    if id.isdigit():
        complaint = db.query(Complaint).filter(Complaint.id == int(id)).first()
    else:
        complaint = db.query(Complaint).filter(Complaint.complaint_number == id).first()

    if not complaint or not verify_complaint_access(complaint, current_user, db):
        raise HTTPException(status_code=404, detail="Complaint not found")

    _enrich_complaint_response(db, complaint)
    return complaint

@router.get("/{id}/graph", response_model=GraphDataResponse)
def get_complaint_graph(
    id: str,
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user)
):
    if id.isdigit():
        complaint = db.query(Complaint).filter(Complaint.id == int(id)).first()
    else:
        complaint = db.query(Complaint).filter(Complaint.complaint_number == id).first()

    if not complaint or not verify_complaint_access(complaint, current_user, db):
        raise HTTPException(status_code=404, detail="Complaint not found")

    return build_complaint_graph(db, complaint.id)
