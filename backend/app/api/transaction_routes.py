from typing import List, Any
from fastapi import APIRouter, Depends, HTTPException, Response
from sqlalchemy.orm import Session
from backend.app.models.db import get_db
from backend.app.models.models import Complaint, Transaction, Account
from backend.app.schemas.schemas import TransactionResponse, TransactionContextResponse, GraphDataResponse
from backend.app.services.transaction_context_service import resolve_transaction_context
from backend.app.services.graph_service import build_complaint_graph

router = APIRouter(prefix="/complaints", tags=["Transactions & Graphs"])

@router.get("/{id}/transactions", response_model=List[TransactionResponse])
def get_complaint_transactions(id: str, response: Response, db: Session = Depends(get_db)):
    if id.isdigit():
        complaint = db.query(Complaint).filter(Complaint.id == int(id)).first()
    else:
        complaint = db.query(Complaint).filter(Complaint.complaint_number == id).first()

    if not complaint:
        raise HTTPException(status_code=404, detail="Complaint not found")

    context = resolve_transaction_context(db, complaint)
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
            "source_scenario": context["source_scenario"]
        })

    return results

@router.get("/{id}/transactions/context", response_model=TransactionContextResponse)
def get_complaint_transaction_context(id: str, db: Session = Depends(get_db)):
    if id.isdigit():
        complaint = db.query(Complaint).filter(Complaint.id == int(id)).first()
    else:
        complaint = db.query(Complaint).filter(Complaint.complaint_number == id).first()

    if not complaint:
        raise HTTPException(status_code=404, detail="Complaint not found")

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
            "source_scenario": context["source_scenario"]
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
def get_complaint_graph(id: str, db: Session = Depends(get_db)):
    if id.isdigit():
        complaint = db.query(Complaint).filter(Complaint.id == int(id)).first()
    else:
        complaint = db.query(Complaint).filter(Complaint.complaint_number == id).first()

    if not complaint:
        raise HTTPException(status_code=404, detail="Complaint not found")

    graph_data = build_complaint_graph(db, complaint.id)
    return graph_data
