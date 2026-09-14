"""
CyberShield AI — Controlled Synthetic Multi-Hop Demo Seed Script
Seed for Complaint: CMP-DL-MULTIHOP-001

Demonstrates real multi-hop financial flow and terminal cash-out endpoints:
- 1 Victim / Source Account (Arun Verma - SBI)
- 2 First-Layer Beneficiary Accounts (Vikram Malhotra - HDFC, Suresh Gupta - ICICI)
- 2 Intermediate Accounts (Rapid Pay Traders - Axis, Apex Digital Services - Kotak)
- 2 Cash-Out ATM Endpoints (ATM-DL-0001, ATM-DL-0002)

Total Nodes: 7 (5 accounts + 2 ATMs)
Total Edges: 7 (5 transactions + 2 withdrawals)
Hop Depth: 3

Idempotency:
Safe to run repeatedly without duplicating records or corrupting database constraints.
"""

import os
import sys
import datetime
from decimal import Decimal

# Ensure project root is in path
sys.path.insert(0, os.path.abspath(os.path.join(os.path.dirname(__file__), "..", "..", "..")))

from backend.app.models.db import SessionLocal
from backend.app.models.models import (
    Complaint, Account, ComplaintAccount, Transaction, Withdrawal, ATMLocation
)

DEMO_COMPLAINT_NUMBER = "CMP-DL-MULTIHOP-001"
ACCOUNT_NUMBERS = [
    "ACC-SYN-MH-1001",
    "ACC-SYN-MH-2001",
    "ACC-SYN-MH-2002",
    "ACC-SYN-MH-3001",
    "ACC-SYN-MH-3002"
]
TRANSACTION_REFS = [
    "UTR-DL-MH-0101",
    "UTR-DL-MH-0102",
    "UTR-DL-MH-0201",
    "UTR-DL-MH-0202",
    "UTR-DL-MH-0203"
]


def seed_multihop_demo(db=None):
    close_db = False
    if db is None:
        db = SessionLocal()
        close_db = True

    try:
        print(f"--- Seeding Controlled Synthetic Multi-Hop Demo: {DEMO_COMPLAINT_NUMBER} ---")

        # 1. Clean existing records for this specific demo to guarantee strict idempotency
        existing_comp = db.query(Complaint).filter(Complaint.complaint_number == DEMO_COMPLAINT_NUMBER).first()
        if existing_comp:
            print(f"  Existing demo complaint found (ID: {existing_comp.id}). Removing previous records for clean re-seed...")
            # Remove associated transactions
            db.query(Transaction).filter(Transaction.complaint_id == existing_comp.id).delete(synchronize_session=False)
            # Remove complaint-account links
            db.query(ComplaintAccount).filter(ComplaintAccount.complaint_id == existing_comp.id).delete(synchronize_session=False)

            # Find demo accounts
            demo_accs = db.query(Account).filter(Account.account_number.in_(ACCOUNT_NUMBERS)).all()
            demo_acc_ids = [a.id for a in demo_accs]
            if demo_acc_ids:
                # Remove withdrawals on demo accounts
                db.query(Withdrawal).filter(Withdrawal.account_id.in_(demo_acc_ids)).delete(synchronize_session=False)
                # Remove transactions where demo accounts are sender or receiver
                db.query(Transaction).filter(
                    (Transaction.sender_account_id.in_(demo_acc_ids)) | (Transaction.receiver_account_id.in_(demo_acc_ids))
                ).delete(synchronize_session=False)
                # Remove accounts
                db.query(Account).filter(Account.id.in_(demo_acc_ids)).delete(synchronize_session=False)

            db.delete(existing_comp)
            db.commit()

        # Also clean up any orphan demo accounts/txs if complaint wasn't present
        orphan_accs = db.query(Account).filter(Account.account_number.in_(ACCOUNT_NUMBERS)).all()
        if orphan_accs:
            o_ids = [a.id for a in orphan_accs]
            db.query(Withdrawal).filter(Withdrawal.account_id.in_(o_ids)).delete(synchronize_session=False)
            db.query(Transaction).filter(
                (Transaction.sender_account_id.in_(o_ids)) | (Transaction.receiver_account_id.in_(o_ids))
            ).delete(synchronize_session=False)
            db.query(ComplaintAccount).filter(ComplaintAccount.account_id.in_(o_ids)).delete(synchronize_session=False)
            db.query(Account).filter(Account.id.in_(o_ids)).delete(synchronize_session=False)
            db.commit()

        # 2. Resolve target ATMs for Cash-Out Endpoints
        atm_1 = db.query(ATMLocation).filter(ATMLocation.atm_code == "ATM-DL-0001").first()
        atm_2 = db.query(ATMLocation).filter(ATMLocation.atm_code == "ATM-DL-0002").first()
        if not atm_1:
            atm_1 = db.query(ATMLocation).first()
        if not atm_2:
            atm_2 = db.query(ATMLocation).offset(1).first() or atm_1

        # 3. Create Complaint
        incident_time = datetime.datetime(2026, 9, 14, 8, 30, 0)
        reported_time = datetime.datetime(2026, 9, 14, 10, 30, 0)

        complaint = Complaint(
            complaint_number=DEMO_COMPLAINT_NUMBER,
            fraud_type="Investment / Task Scam",
            amount=Decimal("150000.00"),
            victim_name="Arun Verma",
            victim_phone="+91 98101 23456",
            victim_location="Connaught Place, Central Delhi",
            state="Delhi",
            district="CENTRAL_NEW_DELHI",
            payment_channel="UPI",
            reported_at=reported_time,
            incident_time=incident_time,
            victim_lat=28.6315,
            victim_lon=77.2167,
            description="[CONTROLLED SYNTHETIC DEMO] Multi-hop layered fund transfer trail from Delhi victim to 2 beneficiary accounts, 2 intermediate accounts, and 2 cash-out ATM endpoints.",
            locality="Connaught Place",
            provenance_mode="CONTROLLED_SYNTHETIC_DEMO",
            risk_level="HIGH",
            risk_score=0.85,
            prediction_status="COMPLETED",
            case_status="ACTIVE",
            created_at=reported_time
        )
        db.add(complaint)
        db.flush()

        # 4. Create 5 Accounts (1 Victim, 2 Beneficiaries, 2 Intermediaries)
        acc_victim = Account(
            account_number="ACC-SYN-MH-1001",
            masked_account="ACC••••1001",
            bank_name="State Bank of India",
            branch="Connaught Circus Branch, New Delhi",
            ifsc="SBIN0000691",
            holder_name="Arun Verma (Victim / Complainant)",
            account_type="SAVINGS",
            state="Delhi",
            district="CENTRAL_NEW_DELHI",
            risk_score=0.05,
            is_mule=False,
            created_at=incident_time - datetime.timedelta(days=120)
        )
        acc_ben_1 = Account(
            account_number="ACC-SYN-MH-2001",
            masked_account="ACC••••2001",
            bank_name="HDFC Bank",
            branch="Barakhamba Road Branch, New Delhi",
            ifsc="HDFC0000003",
            holder_name="Vikram Malhotra (Layer 1 Beneficiary)",
            account_type="SAVINGS",
            state="Delhi",
            district="CENTRAL_NEW_DELHI",
            risk_score=0.65,
            is_mule=False,
            flag_reason="Rapid multi-channel pass-through recipient",
            created_at=incident_time - datetime.timedelta(days=45)
        )
        acc_ben_2 = Account(
            account_number="ACC-SYN-MH-2002",
            masked_account="ACC••••2002",
            bank_name="ICICI Bank",
            branch="Paharganj Branch, Central Delhi",
            ifsc="ICIC0000007",
            holder_name="Suresh Gupta (Layer 1 Beneficiary)",
            account_type="SAVINGS",
            state="Delhi",
            district="CENTRAL_NEW_DELHI",
            risk_score=0.60,
            is_mule=False,
            flag_reason="Immediate downstream transfer following credit",
            created_at=incident_time - datetime.timedelta(days=30)
        )
        acc_inter_1 = Account(
            account_number="ACC-SYN-MH-3001",
            masked_account="ACC••••3001",
            bank_name="Axis Bank",
            branch="Karol Bagh Branch, Central Delhi",
            ifsc="UTIB0000015",
            holder_name="Rapid Pay Traders (Intermediary Account)",
            account_type="CURRENT",
            state="Delhi",
            district="CENTRAL_NEW_DELHI",
            risk_score=0.78,
            is_mule=False,
            flag_reason="High-velocity intermediary aggregator account",
            created_at=incident_time - datetime.timedelta(days=60)
        )
        acc_inter_2 = Account(
            account_number="ACC-SYN-MH-3002",
            masked_account="ACC••••3002",
            bank_name="Kotak Mahindra Bank",
            branch="Rajendra Place Branch, West Delhi",
            ifsc="KKBK0000180",
            holder_name="Apex Digital Services (Intermediary Account)",
            account_type="CURRENT",
            state="Delhi",
            district="WEST_DELHI",
            risk_score=0.72,
            is_mule=False,
            flag_reason="Convergent mule layer pooling account",
            created_at=incident_time - datetime.timedelta(days=90)
        )

        db.add_all([acc_victim, acc_ben_1, acc_ben_2, acc_inter_1, acc_inter_2])
        db.flush()

        # 5. Link Accounts in ComplaintAccount
        db.add_all([
            ComplaintAccount(complaint_id=complaint.id, account_id=acc_victim.id, association_type="VICTIM"),
            ComplaintAccount(complaint_id=complaint.id, account_id=acc_ben_1.id, association_type="BENEFICIARY"),
            ComplaintAccount(complaint_id=complaint.id, account_id=acc_ben_2.id, association_type="BENEFICIARY"),
            ComplaintAccount(complaint_id=complaint.id, account_id=acc_inter_1.id, association_type="INTERMEDIARY"),
            ComplaintAccount(complaint_id=complaint.id, account_id=acc_inter_2.id, association_type="INTERMEDIARY")
        ])
        db.flush()

        # 6. Create 5 Multi-Hop Transactions
        tx_1 = Transaction(
            transaction_ref="UTR-DL-MH-0101",
            complaint_id=complaint.id,
            sender_account_id=acc_victim.id,
            receiver_account_id=acc_ben_1.id,
            amount=Decimal("90000.00"),
            payment_channel="UPI",
            timestamp=datetime.datetime(2026, 9, 14, 8, 35, 0),
            hop_number=1,
            status="COMPLETED",
            suspicious_flag=True
        )
        tx_2 = Transaction(
            transaction_ref="UTR-DL-MH-0102",
            complaint_id=complaint.id,
            sender_account_id=acc_victim.id,
            receiver_account_id=acc_ben_2.id,
            amount=Decimal("60000.00"),
            payment_channel="UPI",
            timestamp=datetime.datetime(2026, 9, 14, 8, 38, 0),
            hop_number=1,
            status="COMPLETED",
            suspicious_flag=True
        )
        tx_3 = Transaction(
            transaction_ref="UTR-DL-MH-0201",
            complaint_id=complaint.id,
            sender_account_id=acc_ben_1.id,
            receiver_account_id=acc_inter_1.id,
            amount=Decimal("85000.00"),
            payment_channel="IMPS",
            timestamp=datetime.datetime(2026, 9, 14, 8, 45, 0),
            hop_number=2,
            status="COMPLETED",
            suspicious_flag=True
        )
        tx_4 = Transaction(
            transaction_ref="UTR-DL-MH-0202",
            complaint_id=complaint.id,
            sender_account_id=acc_ben_2.id,
            receiver_account_id=acc_inter_2.id,
            amount=Decimal("55000.00"),
            payment_channel="NEFT",
            timestamp=datetime.datetime(2026, 9, 14, 8, 48, 0),
            hop_number=2,
            status="COMPLETED",
            suspicious_flag=True
        )
        tx_5 = Transaction(
            transaction_ref="UTR-DL-MH-0203",
            complaint_id=complaint.id,
            sender_account_id=acc_ben_1.id,
            receiver_account_id=acc_inter_2.id,
            amount=Decimal("5000.00"),
            payment_channel="UPI",
            timestamp=datetime.datetime(2026, 9, 14, 8, 52, 0),
            hop_number=2,
            status="COMPLETED",
            suspicious_flag=True
        )

        db.add_all([tx_1, tx_2, tx_3, tx_4, tx_5])
        db.flush()

        # 7. Create 2 Cash-Out Terminal Withdrawals
        wdl_1 = Withdrawal(
            atm_id=atm_1.id,
            account_id=acc_inter_1.id,
            amount=Decimal("45000.00"),
            timestamp=datetime.datetime(2026, 9, 14, 9, 15, 0),
            success=True,
            camera_flagged=True
        )
        wdl_2 = Withdrawal(
            atm_id=atm_2.id,
            account_id=acc_inter_2.id,
            amount=Decimal("50000.00"),
            timestamp=datetime.datetime(2026, 9, 14, 9, 20, 0),
            success=True,
            camera_flagged=False
        )

        db.add_all([wdl_1, wdl_2])
        db.commit()

        print("  Controlled Synthetic Multi-Hop Demo seeded successfully!")
        print(f"  Complaint ID: {complaint.id} ({complaint.complaint_number})")
        print(f"  Accounts: 5, Transactions: 5, Withdrawals: 2")
        print(f"  Target ATMs: {atm_1.atm_code} ({atm_1.bank_name}), {atm_2.atm_code} ({atm_2.bank_name})")
        return complaint.id

    except Exception as e:
        db.rollback()
        print(f"  Error seeding multi-hop demo: {e}")
        raise
    finally:
        if close_db:
            db.close()


if __name__ == "__main__":
    seed_multihop_demo()
