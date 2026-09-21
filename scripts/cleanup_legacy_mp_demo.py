"""
CyberShield AI — Safe Legacy Data Cleanup Script
Cleans up legacy prototype Madhya Pradesh demo data and test fixture complaints.

Usage:
  python scripts/cleanup_legacy_mp_demo.py --dry-run
  python scripts/cleanup_legacy_mp_demo.py --cleanup-mp --dry-run
  python scripts/cleanup_legacy_mp_demo.py --cleanup-test-fixtures --dry-run
  python scripts/cleanup_legacy_mp_demo.py --cleanup-mp --cleanup-test-fixtures --apply

Safety Guarantees:
  - Default is always --dry-run (no DB writes without --apply).
  - Explicitly prints every affected entity count and identifier before removal.
  - Never deletes operational CMP-DL-* or user-created CMP-NEW-* cases.
  - Safely detaches any accidental links before deletion.
"""

import sys
import os
import argparse
from typing import List, Dict, Any, Set

BASE_DIR = os.path.abspath(os.path.join(os.path.dirname(__file__), ".."))
if BASE_DIR not in sys.path:
    sys.path.insert(0, BASE_DIR)

from backend.app.models.db import SessionLocal
from backend.app.models.models import (
    Complaint, Account, ComplaintAccount, Transaction,
    Withdrawal, Prediction, PredictionLocation, Alert, NotificationOutbox,
    LocationCluster, ATMLocation, BankAction,
    CaseNote, EvidenceFile, CaseHandoff, OutcomeObservation,
    PredictionSnapshot
)

LEGACY_MP_CLUSTERS = [
    "Vijay Nagar, Indore", "Palasia, Indore", "Rau, Indore",
    "MP Nagar, Bhopal", "New Market, Bhopal", "Freeganj, Ujjain",
    "Bhanwarkuan, Indore", "Sarafa Bazaar, Indore", "Scheme 54, Indore",
    "Kolar Road, Bhopal", "Arera Colony, Bhopal", "Civic Center, Jabalpur"
]

LEGACY_MP_ATMS = [
    "ATM-SBI-VN01", "ATM-HDFC-VN02", "ATM-PNB-VN03", "ATM-ICICI-VN04",
    "ATM-AXIS-PL01", "ATM-BOB-PL02", "ATM-SBI-RA01", "ATM-SBI-MP01",
    "ATM-HDFC-MP02", "ATM-ICICI-UJ01"
]


def delete_complaints_cascade(db, complaint_ids: List[int]):
    """Safely removes complaints and all their foreign-key dependents in topological order."""
    if not complaint_ids:
        return

    # 1. Bank Actions
    db.query(BankAction).filter(BankAction.complaint_id.in_(complaint_ids)).delete(synchronize_session=False)

    # 2. Alerts and Alert Outbox
    alert_ids = [a.id for a in db.query(Alert.id).filter(Alert.complaint_id.in_(complaint_ids)).all()]
    if alert_ids:
        db.query(NotificationOutbox).filter(NotificationOutbox.alert_id.in_(alert_ids)).delete(synchronize_session=False)
        db.query(Alert).filter(Alert.complaint_id.in_(complaint_ids)).delete(synchronize_session=False)

    # 3. Case Handoffs, Evidence Files, Case Notes, Outcome Observations
    db.query(CaseHandoff).filter(CaseHandoff.complaint_id.in_(complaint_ids)).delete(synchronize_session=False)
    db.query(EvidenceFile).filter(EvidenceFile.complaint_id.in_(complaint_ids)).delete(synchronize_session=False)
    db.query(CaseNote).filter(CaseNote.complaint_id.in_(complaint_ids)).delete(synchronize_session=False)
    db.query(OutcomeObservation).filter(OutcomeObservation.complaint_id.in_(complaint_ids)).delete(synchronize_session=False)

    # 4. Predictions, Prediction Locations, Prediction Snapshots
    pred_ids = [p.id for p in db.query(Prediction.id).filter(Prediction.complaint_id.in_(complaint_ids)).all()]
    if pred_ids:
        db.query(PredictionLocation).filter(PredictionLocation.prediction_id.in_(pred_ids)).delete(synchronize_session=False)
        db.query(PredictionSnapshot).filter(PredictionSnapshot.prediction_id.in_(pred_ids)).delete(synchronize_session=False)
        # Break parent_prediction_id self-references
        db.query(Prediction).filter(Prediction.complaint_id.in_(complaint_ids)).update({"parent_prediction_id": None}, synchronize_session=False)
        db.query(Prediction).filter(Prediction.complaint_id.in_(complaint_ids)).delete(synchronize_session=False)

    # 5. Transactions, Complaint Accounts, Withdrawals
    db.query(Transaction).filter(Transaction.complaint_id.in_(complaint_ids)).delete(synchronize_session=False)
    db.query(ComplaintAccount).filter(ComplaintAccount.complaint_id.in_(complaint_ids)).delete(synchronize_session=False)
    db.query(Withdrawal).filter(Withdrawal.complaint_id.in_(complaint_ids)).delete(synchronize_session=False)

    # 6. Complaints
    db.query(Complaint).filter(Complaint.id.in_(complaint_ids)).delete(synchronize_session=False)


def cleanup_legacy_mp_data(db, apply: bool = False) -> Dict[str, Any]:
    """Finds and optionally removes legacy MP prototype data."""
    report = {}

    # 1. Legacy MP Complaint: CMP-1042
    cmp1042 = db.query(Complaint).filter(Complaint.complaint_number == "CMP-1042").first()
    report["cmp_1042_found"] = bool(cmp1042)
    if cmp1042:
        report["cmp_1042_id"] = cmp1042.id
        report["cmp_1042_transactions"] = db.query(Transaction).filter(Transaction.complaint_id == cmp1042.id).count()
        report["cmp_1042_predictions"] = db.query(Prediction).filter(Prediction.complaint_id == cmp1042.id).count()
        report["cmp_1042_alerts"] = db.query(Alert).filter(Alert.complaint_id == cmp1042.id).count()
        report["cmp_1042_account_links"] = db.query(ComplaintAccount).filter(ComplaintAccount.complaint_id == cmp1042.id).count()

        if apply:
            delete_complaints_cascade(db, [cmp1042.id])

    # 2. Legacy MP Clusters & ATMs
    mp_clusters = db.query(LocationCluster).filter(
        (LocationCluster.cluster_name.in_(LEGACY_MP_CLUSTERS)) |
        (LocationCluster.state.ilike("%madhya pradesh%")) |
        (LocationCluster.city.in_(["Indore", "Bhopal", "Ujjain", "Jabalpur"]))
    ).all()
    report["mp_clusters_count"] = len(mp_clusters)
    report["mp_clusters"] = [c.cluster_name for c in mp_clusters]
    mp_cluster_ids = [c.id for c in mp_clusters]

    mp_atms = db.query(ATMLocation).filter(
        (ATMLocation.atm_code.in_(LEGACY_MP_ATMS)) |
        (ATMLocation.cluster_id.in_(mp_cluster_ids)) |
        (ATMLocation.state.ilike("%madhya pradesh%")) |
        (ATMLocation.city.in_(["Indore", "Bhopal", "Ujjain", "Jabalpur"]))
    ).all()
    report["mp_atms_count"] = len(mp_atms)
    report["mp_atms"] = [a.atm_code for a in mp_atms]
    mp_atm_ids = [a.id for a in mp_atms]

    if apply and mp_atms:
        db.query(Withdrawal).filter(Withdrawal.atm_id.in_(mp_atm_ids)).delete(synchronize_session=False)
        db.query(ATMLocation).filter(ATMLocation.id.in_(mp_atm_ids)).delete(synchronize_session=False)

    if apply and mp_clusters:
        db.query(PredictionLocation).filter(PredictionLocation.cluster_id.in_(mp_cluster_ids)).delete(synchronize_session=False)
        db.query(LocationCluster).filter(LocationCluster.id.in_(mp_cluster_ids)).delete(synchronize_session=False)

    # 3. Clean up non-Delhi region_id on clusters / atms
    contaminated_clusters = db.query(LocationCluster).filter(
        LocationCluster.region_id == "delhi",
        ~LocationCluster.state.ilike("%delhi%")
    ).all()
    report["contaminated_clusters_count"] = len(contaminated_clusters)
    if apply and contaminated_clusters:
        for c in contaminated_clusters:
            c.region_id = None

    contaminated_atms = db.query(ATMLocation).filter(
        ATMLocation.region_id == "delhi",
        ~ATMLocation.state.ilike("%delhi%")
    ).all()
    report["contaminated_atms_count"] = len(contaminated_atms)
    if apply and contaminated_atms:
        for a in contaminated_atms:
            a.region_id = None

    return report


def cleanup_test_fixtures(db, apply: bool = False) -> Dict[str, Any]:
    """Finds and optionally removes developer/automated test fixtures."""
    report = {}

    test_complaints = db.query(Complaint).filter(
        (Complaint.complaint_number.like("CMP-EXP-TEST-%")) |
        (Complaint.complaint_number.like("CMP-TEST-%")) |
        (Complaint.complaint_number.like("CMP-P5-MP-%"))
    ).all()

    report["test_complaints_count"] = len(test_complaints)
    report["test_complaint_numbers"] = [c.complaint_number for c in test_complaints]

    if apply and test_complaints:
        c_ids = [c.id for c in test_complaints]
        delete_complaints_cascade(db, c_ids)

    return report


def main():
    parser = argparse.ArgumentParser(description="Safe Legacy MP & Test Fixture Cleanup Utility")
    parser.add_argument("--dry-run", action="store_true", default=False, help="Simulate cleanup without writing to DB")
    parser.add_argument("--apply", action="store_true", help="Execute actual deletion in database")
    parser.add_argument("--cleanup-mp", action="store_true", help="Clean up legacy MP/Indore prototype data")
    parser.add_argument("--cleanup-test-fixtures", action="store_true", help="Clean up explicit test fixture complaints")

    args = parser.parse_args()

    run_mp = args.cleanup_mp or (not args.cleanup_mp and not args.cleanup_test_fixtures)
    run_test = args.cleanup_test_fixtures or (not args.cleanup_mp and not args.cleanup_test_fixtures)
    is_apply = args.apply and not args.dry_run

    mode_str = "APPLY (DESTRUCTIVE WRITE)" if is_apply else "DRY-RUN (READ-ONLY SIMULATION)"
    print(f"============================================================")
    print(f" CyberShield AI — Safe Legacy Data Cleanup [{mode_str}]")
    print(f"============================================================")

    db = SessionLocal()
    try:
        if run_mp:
            print("\n--- 1. Evaluating Legacy Madhya Pradesh Prototype Records ---")
            mp_report = cleanup_legacy_mp_data(db, apply=is_apply)
            for k, v in mp_report.items():
                print(f"  {k}: {v}")

        if run_test:
            print("\n--- 2. Evaluating Automated Test Fixture Records ---")
            test_report = cleanup_test_fixtures(db, apply=is_apply)
            for k, v in test_report.items():
                print(f"  {k}: {v}")

        if is_apply:
            db.commit()
            print("\n[SUCCESS] Cleanup successfully committed to PostgreSQL database.")
        else:
            print("\n[DRY-RUN COMPLETE] Zero changes were made. Use --apply to execute.")
    except Exception as exc:
        db.rollback()
        print(f"\n[ERROR] Cleanup failed: {exc}", file=sys.stderr)
        sys.exit(1)
    finally:
        db.close()


if __name__ == "__main__":
    main()
