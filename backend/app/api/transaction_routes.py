import logging
from datetime import datetime
from typing import List, Any, Optional, Dict
from fastapi import APIRouter, Depends, HTTPException, Response, status
from sqlalchemy.exc import IntegrityError
from sqlalchemy.orm import Session
from backend.app.models.db import get_db
from backend.app.models.models import Complaint, Transaction, Account, User
from backend.app.schemas.schemas import (
    TransactionResponse,
    TransactionContextResponse,
    GraphDataResponse,
    TransactionIngestRequest,
    TransactionCorrectionRequest,
    TransactionIngestResponse,
)
from backend.app.services.transaction_context_service import resolve_transaction_context
from backend.app.services.graph_service import build_complaint_graph
from backend.app.services.prediction_service import prediction_service
from backend.app.auth.security import get_current_user
from backend.app.auth.rbac import (
    verify_complaint_access, require_roles, resolve_bank_organization_id, RoleEnum
)

logger = logging.getLogger(__name__)

router = APIRouter(prefix="/complaints", tags=["Transactions & Graphs"])


@router.post("/{id}/transactions", response_model=TransactionIngestResponse, status_code=status.HTTP_201_CREATED)
def ingest_complaint_transaction(
    id: str,
    req: TransactionIngestRequest,
    response: Response,
    db: Session = Depends(get_db),
    current_user: User = Depends(require_roles(
        RoleEnum.I4C_ADMIN, RoleEnum.STATE_LEA, RoleEnum.DISTRICT_LEA, RoleEnum.ANALYST
    ))
):
    """
    Authenticated transaction ingestion endpoint with:
    - Server-controlled received_at and provenance enforcement (rejects client claims of BANK_API).
    - Deduplication: identical replay returns existing transaction idempotently (200 OK + header).
    - Anti-enumeration: cross-case conflicts return generic conflict with zero existence disclosure.
    - Concurrency safety: handles race conditions via DB unique constraint without pre-select reliance.
    - Automatic predictive intelligence recalculation using the transfer cutoff.
    """
    if id.isdigit():
        complaint = db.query(Complaint).filter(Complaint.id == int(id)).first()
    else:
        complaint = db.query(Complaint).filter(Complaint.complaint_number == id).first()

    if not complaint or not verify_complaint_access(complaint, current_user, db):
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Complaint not found")

    # If correction_of_ref is provided, verify original transaction belongs to this complaint
    if req.correction_of_ref:
        orig_tx = db.query(Transaction).filter(Transaction.transaction_ref == req.correction_of_ref).first()
        if not orig_tx or orig_tx.complaint_id != complaint.id:
            raise HTTPException(
                status_code=status.HTTP_404_NOT_FOUND,
                detail="Original transaction reference not found for this complaint."
            )

    # 1. Check for existing transaction reference (deduplication / conflict)
    existing = db.query(Transaction).filter(Transaction.transaction_ref == req.transaction_ref).first()
    if existing:
        if existing.complaint_id != complaint.id:
            # Generic anti-enumeration response: never disclose cross-case reference existence
            raise HTTPException(
                status_code=status.HTTP_409_CONFLICT,
                detail="Transaction reference conflict detected or reference unavailable."
            )
        # Verify if payload is identical
        sender_acc = existing.sender
        receiver_acc = existing.receiver
        is_identical = (
            abs(float(existing.amount) - float(req.amount)) < 0.001
            and (existing.payment_channel or "UPI").upper() == (req.payment_channel or "UPI").upper()
            and abs((existing.timestamp - req.timestamp).total_seconds()) < 1.0
            and (sender_acc.account_number if sender_acc else "") == req.sender_account_number
            and (receiver_acc.account_number if receiver_acc else "") == req.receiver_account_number
            and (existing.is_reversal == (req.is_reversal or False))
            and (existing.correction_of_ref == req.correction_of_ref)
        )
        if is_identical:
            response.status_code = status.HTTP_200_OK
            response.headers["X-Idempotent-Replay"] = "true"
            return TransactionIngestResponse(
                id=existing.id,
                transaction_ref=existing.transaction_ref,
                amount=float(existing.amount),
                payment_channel=existing.payment_channel,
                timestamp=existing.timestamp,
                received_at=existing.received_at,
                source_system=existing.source_system or "DIRECT_OFFICER_INPUT",
                analysis_status=existing.analysis_status or "COMPLETED",
                prediction_id=existing.prediction_id,
                is_idempotent_replay=True,
                message="Identical transaction already ingested. Returned existing record idempotently.",
                is_reversal=existing.is_reversal,
                correction_of_ref=existing.correction_of_ref,
                created_by_user_id=existing.created_by_user_id,
            )
        else:
            raise HTTPException(
                status_code=status.HTTP_409_CONFLICT,
                detail=f"Conflict: Transaction '{req.transaction_ref}' already exists with differing payload parameters. Authorized correction workflow required."
            )

    # 2. Resolve or create sender and receiver accounts without fabricated defaults
    sender = db.query(Account).filter(Account.account_number == req.sender_account_number).first()
    if not sender:
        masked = f"ACC••••{req.sender_account_number[-4:]}" if len(req.sender_account_number) >= 4 else req.sender_account_number
        sender = Account(
            account_number=req.sender_account_number,
            masked_account=masked,
            bank_name=req.sender_bank or "UNKNOWN",
            bank_organization_id=resolve_bank_organization_id(db, req.sender_bank),
            branch=None,
            ifsc=None,
            holder_name=f"Sender ({masked})",
            account_type=None,
            state=complaint.state,
            district=complaint.district,
            risk_score=None,
            is_mule=False
        )
        db.add(sender)
        db.flush()

    receiver = db.query(Account).filter(Account.account_number == req.receiver_account_number).first()
    if not receiver:
        masked_r = f"ACC••••{req.receiver_account_number[-4:]}" if len(req.receiver_account_number) >= 4 else req.receiver_account_number
        receiver = Account(
            account_number=req.receiver_account_number,
            masked_account=masked_r,
            bank_name=req.receiver_bank or "UNKNOWN",
            bank_organization_id=resolve_bank_organization_id(db, req.receiver_bank),
            branch=None,
            ifsc=None,
            holder_name=f"Beneficiary ({masked_r})",
            account_type=None,
            state=complaint.state,
            district=complaint.district,
            risk_score=None,
            is_mule=False
        )
        db.add(receiver)
        db.flush()

    # 3. Server-controlled received_at and source identity
    server_received_at = datetime.utcnow()
    # LEA officers cannot claim BANK_API status: server binds source identity to user context
    user_roles = [r.name if hasattr(r, "name") else str(r) for r in getattr(current_user, "roles", [])]
    trusted_source = "BANK_API" if "BANK_API" in user_roles and req.source_system == "BANK_API" else "DIRECT_OFFICER_INPUT"
    dedup_key = f"{req.transaction_ref}:{req.sender_account_number}:{req.receiver_account_number}:{float(req.amount):.2f}"

    new_tx = Transaction(
        transaction_ref=req.transaction_ref,
        complaint_id=complaint.id,
        sender_account_id=sender.id,
        receiver_account_id=receiver.id,
        amount=req.amount,
        payment_channel=req.payment_channel or "UPI",
        timestamp=req.timestamp,
        received_at=server_received_at,
        source_system=trusted_source,
        dedup_key=dedup_key,
        is_reversal=bool(req.is_reversal),
        correction_of_ref=req.correction_of_ref,
        hop_number=req.hop_number or 1,
        status="COMPLETED",
        analysis_status="PENDING",
        prediction_id=None,
        suspicious_flag=req.suspicious_flag if req.suspicious_flag is not None else True,
        created_by_user_id=current_user.id,
    )

    try:
        db.add(new_tx)
        db.commit()
        db.refresh(new_tx)
    except IntegrityError as ie:
        db.rollback()
        err_str = str(ie).lower()
        is_ref_conflict = (
            "uq_transactions_transaction_ref" in err_str
            or "transaction_ref" in err_str
            or "unique constraint" in err_str
        )
        if is_ref_conflict:
            winner = db.query(Transaction).filter(Transaction.transaction_ref == req.transaction_ref).first()
            if winner and winner.complaint_id == complaint.id:
                winner_s = winner.sender
                winner_r = winner.receiver
                is_ident = (
                    abs(float(winner.amount) - float(req.amount)) < 0.001
                    and (winner.payment_channel or "UPI").upper() == (req.payment_channel or "UPI").upper()
                    and abs((winner.timestamp - req.timestamp).total_seconds()) < 1.0
                    and (winner_s.account_number if winner_s else "") == req.sender_account_number
                    and (winner_r.account_number if winner_r else "") == req.receiver_account_number
                    and (winner.is_reversal == (req.is_reversal or False))
                    and (winner.correction_of_ref == req.correction_of_ref)
                )
                if is_ident:
                    response.status_code = status.HTTP_200_OK
                    response.headers["X-Idempotent-Replay"] = "true"
                    return TransactionIngestResponse(
                        id=winner.id,
                        transaction_ref=winner.transaction_ref,
                        amount=float(winner.amount),
                        payment_channel=winner.payment_channel,
                        timestamp=winner.timestamp,
                        received_at=winner.received_at,
                        source_system=winner.source_system or "DIRECT_OFFICER_INPUT",
                        analysis_status=winner.analysis_status or "COMPLETED",
                        prediction_id=winner.prediction_id,
                        is_idempotent_replay=True,
                        message="Identical transaction already ingested. Returned existing record idempotently.",
                        is_reversal=winner.is_reversal,
                        correction_of_ref=winner.correction_of_ref,
                        created_by_user_id=winner.created_by_user_id,
                    )
            raise HTTPException(
                status_code=status.HTTP_409_CONFLICT,
                detail="Transaction reference conflict detected or reference unavailable."
            )
        raise

    # 4. Trigger new predictive intelligence with cutoff established at server_received_at
    # so that newly received past transfers satisfy both received_at <= cutoff and transaction_time <= cutoff
    analysis_status = "COMPLETED"
    pred_id = None
    try:
        analysis_res = prediction_service.run_and_persist_prediction(
            db, complaint.id, analysis_as_of=server_received_at, analysis_purpose="OPERATIONAL"
        )
        pred_id = getattr(analysis_res, "id", None) or (analysis_res.get("prediction_id") if isinstance(analysis_res, dict) else None)
        if pred_id:
            analysis_status = "COMPLETED"
        else:
            analysis_status = "FAILED_RETRY_REQUIRED"
    except Exception as exc:
        logger.error(
            f"Post-transfer prediction recalculation failed for complaint {complaint.complaint_number}: {exc}",
            exc_info=True
        )
        analysis_status = "FAILED_RETRY_REQUIRED"
        pred_id = None

    new_tx.analysis_status = analysis_status
    new_tx.prediction_id = pred_id
    db.commit()
    db.refresh(new_tx)

    return TransactionIngestResponse(
        id=new_tx.id,
        transaction_ref=new_tx.transaction_ref,
        amount=float(new_tx.amount),
        payment_channel=new_tx.payment_channel,
        timestamp=new_tx.timestamp,
        received_at=new_tx.received_at,
        source_system=new_tx.source_system,
        analysis_status=analysis_status,
        prediction_id=pred_id,
        is_idempotent_replay=False,
        is_reversal=new_tx.is_reversal,
        correction_of_ref=new_tx.correction_of_ref,
        created_by_user_id=new_tx.created_by_user_id,
        message=(
            "Transaction ingested and predictive intelligence recalculated."
            if analysis_status == "COMPLETED"
            else "Transaction ingested. Predictive recalculation failed and requires retry."
        )
    )


@router.post("/{id}/transactions/correction", response_model=TransactionIngestResponse, status_code=status.HTTP_201_CREATED)
def correct_complaint_transaction(
    id: str,
    req: TransactionCorrectionRequest,
    response: Response,
    db: Session = Depends(get_db),
    current_user: User = Depends(require_roles(
        RoleEnum.I4C_ADMIN, RoleEnum.STATE_LEA, RoleEnum.DISTRICT_LEA
    ))
):
    """
    Authorized transaction correction/reversal API:
    - Strictly allows only I4C_ADMIN, STATE_LEA, and DISTRICT_LEA.
    - Verifies role and jurisdiction access for the complaint (404 for wrong jurisdiction).
    - Verifies the target transaction exists under this complaint without revealing other cases.
    - Rejects circular, self-referential, or invalid correction chains.
    - Preserves the original transaction completely untouched.
    - Creates a separate correction/reversal transaction record.
    - Recalculates an OPERATIONAL prediction producing a new monotonic prediction version.
    """
    if id.isdigit():
        complaint = db.query(Complaint).filter(Complaint.id == int(id)).first()
    else:
        complaint = db.query(Complaint).filter(Complaint.complaint_number == id).first()

    if not complaint or not verify_complaint_access(complaint, current_user, db):
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Complaint not found")

    if req.transaction_ref == req.correction_of_ref:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="Circular correction detected: transaction cannot correct itself."
        )

    orig_tx = db.query(Transaction).filter(Transaction.transaction_ref == req.correction_of_ref).first()
    if not orig_tx or orig_tx.complaint_id != complaint.id:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="Original transaction reference not found for this complaint."
        )

    if orig_tx.is_reversal:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="Cannot correct or reverse an already reversed transaction."
        )

    # Check for existing reversal of orig_tx
    existing_reversal = db.query(Transaction).filter(
        Transaction.complaint_id == complaint.id,
        Transaction.correction_of_ref == orig_tx.transaction_ref,
        Transaction.is_reversal == True
    ).first()
    if existing_reversal:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="Transaction has already been reversed."
        )

    # Check ancestry for cycles
    curr_anc = orig_tx
    visited_anc = {orig_tx.transaction_ref}
    while curr_anc.correction_of_ref:
        if curr_anc.correction_of_ref == req.transaction_ref:
            raise HTTPException(
                status_code=status.HTTP_400_BAD_REQUEST,
                detail="Circular correction chain detected."
            )
        curr_anc = db.query(Transaction).filter(
            Transaction.transaction_ref == curr_anc.correction_of_ref,
            Transaction.complaint_id == complaint.id
        ).first()
        if not curr_anc or curr_anc.transaction_ref in visited_anc:
            break
        visited_anc.add(curr_anc.transaction_ref)

    # Defaults from original transaction if omitted
    sender_num = req.sender_account_number or (orig_tx.sender.account_number if orig_tx.sender else None)
    receiver_num = req.receiver_account_number or (orig_tx.receiver.account_number if orig_tx.receiver else None)
    amount_val = req.amount if req.amount is not None else float(orig_tx.amount)
    timestamp_val = req.timestamp or datetime.utcnow()
    channel_val = req.payment_channel or orig_tx.payment_channel or "UPI"

    if not sender_num or not receiver_num:
        raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail="Sender and receiver account numbers are required.")

    ingest_req = TransactionIngestRequest(
        transaction_ref=req.transaction_ref,
        sender_account_number=sender_num,
        receiver_account_number=receiver_num,
        amount=amount_val,
        payment_channel=channel_val,
        timestamp=timestamp_val,
        source_system=req.source_system or "DIRECT_OFFICER_INPUT",
        sender_bank=req.sender_bank,
        receiver_bank=req.receiver_bank,
        hop_number=req.hop_number or orig_tx.hop_number,
        suspicious_flag=req.suspicious_flag if req.suspicious_flag is not None else orig_tx.suspicious_flag,
        is_reversal=req.is_reversal,
        correction_of_ref=req.correction_of_ref,
    )
    return ingest_complaint_transaction(id=id, req=ingest_req, response=response, db=db, current_user=current_user)


@router.post("/{id}/transactions/reversal", response_model=TransactionIngestResponse, status_code=status.HTTP_201_CREATED)
def reverse_complaint_transaction(
    id: str,
    req: TransactionCorrectionRequest,
    response: Response,
    db: Session = Depends(get_db),
    current_user: User = Depends(require_roles(
        RoleEnum.I4C_ADMIN, RoleEnum.STATE_LEA, RoleEnum.DISTRICT_LEA
    ))
):
    """
    Dedicated reversal endpoint: forces is_reversal=True.
    """
    req.is_reversal = True
    return correct_complaint_transaction(id=id, req=req, response=response, db=db, current_user=current_user)


@router.post("/{complaint_id}/transactions/{tx_id}/retry-analysis", response_model=TransactionIngestResponse)
def retry_transaction_analysis(
    complaint_id: str,
    tx_id: int,
    db: Session = Depends(get_db),
    current_user: User = Depends(require_roles(
        RoleEnum.I4C_ADMIN, RoleEnum.STATE_LEA, RoleEnum.DISTRICT_LEA, RoleEnum.ANALYST
    ))
):
    if complaint_id.isdigit():
        complaint = db.query(Complaint).filter(Complaint.id == int(complaint_id)).first()
    else:
        complaint = db.query(Complaint).filter(Complaint.complaint_number == complaint_id).first()

    if not complaint or not verify_complaint_access(complaint, current_user, db):
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Complaint not found")

    tx = db.query(Transaction).filter(Transaction.id == tx_id, Transaction.complaint_id == complaint.id).first()
    if not tx:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Transaction not found for this complaint")

    analysis_status = "COMPLETED"
    pred_id = None
    try:
        analysis_res = prediction_service.run_and_persist_prediction(
            db, complaint.id, analysis_as_of=None, analysis_purpose="OPERATIONAL"
        )
        pred_id = getattr(analysis_res, "id", None) or (analysis_res.get("prediction_id") if isinstance(analysis_res, dict) else None)
        if pred_id:
            analysis_status = "COMPLETED"
        else:
            analysis_status = "FAILED_RETRY_REQUIRED"
    except Exception as exc:
        logger.error(f"Retry prediction recalculation failed for complaint {complaint.complaint_number}: {exc}", exc_info=True)
        analysis_status = "FAILED_RETRY_REQUIRED"
        pred_id = None

    tx.analysis_status = analysis_status
    if pred_id:
        tx.prediction_id = pred_id
    db.commit()
    db.refresh(tx)

    return TransactionIngestResponse(
        id=tx.id,
        transaction_ref=tx.transaction_ref,
        amount=float(tx.amount),
        payment_channel=tx.payment_channel,
        timestamp=tx.timestamp,
        received_at=tx.received_at,
        source_system=tx.source_system or "DIRECT_OFFICER_INPUT",
        analysis_status=tx.analysis_status or "COMPLETED",
        prediction_id=tx.prediction_id,
        is_idempotent_replay=False,
        is_reversal=tx.is_reversal,
        correction_of_ref=tx.correction_of_ref,
        created_by_user_id=tx.created_by_user_id,
        message="Transaction analysis recalculated successfully." if analysis_status == "COMPLETED" else "Retry failed."
    )


@router.get("/{id}/transactions", response_model=List[TransactionResponse])
def get_complaint_transactions(
    id: str,
    response: Response,
    as_of: Optional[datetime] = None,
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user)
):
    if id.isdigit():
        complaint = db.query(Complaint).filter(Complaint.id == int(id)).first()
    else:
        complaint = db.query(Complaint).filter(Complaint.complaint_number == id).first()

    if not complaint or not verify_complaint_access(complaint, current_user, db):
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Complaint not found")

    context = resolve_transaction_context(db, complaint, analysis_as_of=as_of)
    transactions = context["transactions"]

    # Set provenance headers
    response.headers["X-Context-Type"] = context["context_type"]
    response.headers["X-Source-Scenario"] = context["source_scenario"] or ""
    response.headers["X-Transaction-Count"] = str(context["transaction_count"])

    # Pre-fetch accounts for mapping
    acc_ids = set()
    for tx in transactions:
        acc_ids.add(tx.sender_account_id)
        acc_ids.add(tx.receiver_account_id)

    accounts = {acc.id: acc for acc in db.query(Account).filter(Account.id.in_(acc_ids)).all()} if acc_ids else {}

    results = []
    for tx in transactions:
        sender = accounts.get(tx.sender_account_id)
        receiver = accounts.get(tx.receiver_account_id)
        results.append({
            "id": tx.id,
            "transaction_ref": tx.transaction_ref,
            "sender_account": sender.masked_account if sender else "ACC••••0000",
            "receiver_account": receiver.masked_account if receiver else "ACC••••1111",
            "sender_bank": sender.bank_name if sender else "Unknown Bank",
            "receiver_bank": receiver.bank_name if receiver else "Unknown Bank",
            "amount": tx.amount,
            "payment_channel": tx.payment_channel,
            "timestamp": tx.timestamp,
            "hop_number": tx.hop_number,
            "status": tx.status,
            "suspicious_flag": tx.suspicious_flag,
            "context_type": context["context_type"],
            "source_scenario": context["source_scenario"],
            "received_at": getattr(tx, "received_at", None),
            "source_system": getattr(tx, "source_system", "DIRECT_OFFICER_INPUT"),
            "dedup_key": getattr(tx, "dedup_key", None),
            "analysis_status": getattr(tx, "analysis_status", "COMPLETED"),
            "prediction_id": getattr(tx, "prediction_id", None),
            "is_reversal": getattr(tx, "is_reversal", False),
            "correction_of_ref": getattr(tx, "correction_of_ref", None),
            "created_by_user_id": getattr(tx, "created_by_user_id", None),
        })
    return results


@router.get("/{id}/transactions/context", response_model=TransactionContextResponse)
def get_complaint_transaction_context(
    id: str,
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user)
):
    if id.isdigit():
        complaint = db.query(Complaint).filter(Complaint.id == int(id)).first()
    else:
        complaint = db.query(Complaint).filter(Complaint.complaint_number == id).first()

    if not complaint or not verify_complaint_access(complaint, current_user, db):
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Complaint not found")

    context = resolve_transaction_context(db, complaint)
    transactions = context["transactions"]

    acc_ids = set()
    for tx in transactions:
        acc_ids.add(tx.sender_account_id)
        acc_ids.add(tx.receiver_account_id)

    accounts = {acc.id: acc for acc in db.query(Account).filter(Account.id.in_(acc_ids)).all()} if acc_ids else {}

    mapped_txs = []
    for tx in transactions:
        sender = accounts.get(tx.sender_account_id)
        receiver = accounts.get(tx.receiver_account_id)
        mapped_txs.append({
            "id": tx.id,
            "transaction_ref": tx.transaction_ref,
            "sender_account": sender.masked_account if sender else "ACC••••0000",
            "receiver_account": receiver.masked_account if receiver else "ACC••••1111",
            "sender_bank": sender.bank_name if sender else "Unknown Bank",
            "receiver_bank": receiver.bank_name if receiver else "Unknown Bank",
            "amount": tx.amount,
            "payment_channel": tx.payment_channel,
            "timestamp": tx.timestamp,
            "hop_number": tx.hop_number,
            "status": tx.status,
            "suspicious_flag": tx.suspicious_flag,
            "context_type": context["context_type"],
            "source_scenario": context["source_scenario"],
            "received_at": getattr(tx, "received_at", None),
            "source_system": getattr(tx, "source_system", "DIRECT_OFFICER_INPUT"),
            "dedup_key": getattr(tx, "dedup_key", None),
        })

    return {
        "complaint_number": context["complaint_number"],
        "context_type": context["context_type"],
        "source_scenario": context["source_scenario"],
        "transaction_count": context["transaction_count"],
        "provenance": context["provenance"],
        "transactions": mapped_txs
    }


@router.get("/{id}/graph", response_model=GraphDataResponse)
def get_complaint_graph(
    id: str,
    as_of: Optional[datetime] = None,
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user)
):
    if id.isdigit():
        complaint = db.query(Complaint).filter(Complaint.id == int(id)).first()
    else:
        complaint = db.query(Complaint).filter(Complaint.complaint_number == id).first()

    if not complaint or not verify_complaint_access(complaint, current_user, db):
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Complaint not found")

    graph_data = build_complaint_graph(db, complaint.id, analysis_as_of=as_of)
    return graph_data
