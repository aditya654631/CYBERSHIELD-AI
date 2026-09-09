from typing import List, Any
from fastapi import APIRouter, Depends, HTTPException
from sqlalchemy.orm import Session
from backend.app.models.db import get_db
from backend.app.models.models import Complaint, Transaction, Account
from backend.app.schemas.schemas import TransactionResponse, GraphDataResponse
from backend.app.services.graph_service import build_complaint_graph
from backend.app.services.audit_service import log_audit

router = APIRouter(prefix="/complaints", tags=["Transactions & Graphs"])

@router.get("/{id}/transactions", response_model=List[TransactionResponse])
def get_complaint_transactions(id: str, db: Session = Depends(get_db)):
    if id.isdigit():
        complaint = db.query(Complaint).filter(Complaint.id == int(id)).first()
    else:
        complaint = db.query(Complaint).filter(Complaint.complaint_number == id).first()

    if not complaint:
        raise HTTPException(status_code=404, detail="Complaint not found")

    transactions = db.query(Transaction).filter(Transaction.complaint_id == complaint.id).all()

    # Pre-fetch accounts for mapping
    acc_ids = set()
    for tx in transactions:
        acc_ids.add(tx.sender_account_id)
        acc_ids.add(tx.receiver_account_id)

    accounts = {acc.id: acc for acc in db.query(Account).filter(Account.id.in_(acc_ids)).all()}

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
            "suspicious_flag": tx.suspicious_flag
        })

    return results

@router.get("/{id}/graph", response_model=GraphDataResponse)
def get_complaint_graph(id: str, db: Session = Depends(get_db)):
    if id.isdigit():
        complaint = db.query(Complaint).filter(Complaint.id == int(id)).first()
    else:
        complaint = db.query(Complaint).filter(Complaint.complaint_number == id).first()

    if not complaint:
        raise HTTPException(status_code=404, detail="Complaint not found")

    graph_data = build_complaint_graph(db, complaint.id)

    # Log audit
    log_audit(
        db=db,
        officer_name="Inspector R. Verma",
        role="STATE_LEA",
        action="NETWORK_VIEWED",
        case_number=complaint.complaint_number,
        details=f"Financial transaction graph rendered for {complaint.complaint_number} ({len(graph_data['nodes'])} nodes)"
    )

    return graph_data
