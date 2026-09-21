import time
import sys
import os

BASE_DIR = os.path.abspath(os.path.join(os.path.dirname(__file__), "..", ".."))
if BASE_DIR not in sys.path:
    sys.path.insert(0, BASE_DIR)

from backend.app.models.db import SessionLocal
from backend.app.models.models import (
    Complaint, Account, Transaction, ComplaintAccount, Withdrawal,
    LocationCluster, ATMLocation, User, Organization,
    Alert, Prediction, PredictionLocation, PredictionSnapshot,
    BankAction, NotificationOutbox, EvidenceFile, CaseNote,
    CaseHandoff, OutcomeObservation
)
from database.seed.synthetic_generator import DelhiSyntheticDataGenerator
from database.seed.seed_config import (
    SYNTHETIC_RANDOM_SEED, NUM_COMPLAINTS, NUM_ACCOUNTS,
    COMPLAINT_PREFIX, ACCOUNT_PREFIX, TRANSACTION_PREFIX
)

def run():
    db = SessionLocal()
    print("======================================================================")
    print("CYBERSHIELD AI — SAFE SYNTHETIC DATASET V2 REGENERATION")
    print("======================================================================")
    t0 = time.time()

    # Step A: Inspect current counts before touching PostgreSQL
    print("\n--- A. PRE-GENERATION DATABASE COUNTS ---")
    pre_users = db.query(User).count()
    pre_orgs = db.query(Organization).count()
    pre_clusters = db.query(LocationCluster).count()
    pre_delhi_clusters = db.query(LocationCluster).filter(LocationCluster.state == "Delhi").count()
    pre_mp_clusters = db.query(LocationCluster).filter(LocationCluster.state != "Delhi").count()
    pre_atms = db.query(ATMLocation).count()
    pre_delhi_atms = db.query(ATMLocation).filter(ATMLocation.atm_code.like("ATM-DL-%")).count()
    pre_mp_atms = db.query(ATMLocation).filter(~ATMLocation.atm_code.like("ATM-DL-%")).count()

    pre_complaints = db.query(Complaint).count()
    pre_delhi_comp = db.query(Complaint).filter(Complaint.complaint_number.like(f"{COMPLAINT_PREFIX}%")).count()
    pre_cmp1042 = db.query(Complaint).filter(Complaint.complaint_number == "CMP-1042").count()
    pre_other_comp = pre_complaints - pre_delhi_comp

    pre_accounts = db.query(Account).count()
    pre_syn_acc = db.query(Account).filter(Account.account_number.like(f"{ACCOUNT_PREFIX}%")).count()
    pre_other_acc = pre_accounts - pre_syn_acc

    pre_txns = db.query(Transaction).count()
    pre_syn_txns = db.query(Transaction).filter(Transaction.transaction_ref.like(f"{TRANSACTION_PREFIX}%")).count()
    pre_other_txns = pre_txns - pre_syn_txns

    pre_wdls = db.query(Withdrawal).count()
    pre_ca = db.query(ComplaintAccount).count()

    print(f"  Users: {pre_users}, Orgs: {pre_orgs}")
    print(f"  Clusters: {pre_clusters} ({pre_delhi_clusters} Delhi, {pre_mp_clusters} Non-Delhi)")
    print(f"  ATMs: {pre_atms} ({pre_delhi_atms} Delhi, {pre_mp_atms} Non-Delhi)")
    print(f"  Complaints: {pre_complaints} ({pre_delhi_comp} Delhi synthetic, {pre_cmp1042} CMP-1042, {pre_other_comp} total prototype)")
    print(f"  Accounts: {pre_accounts} ({pre_syn_acc} synthetic, {pre_other_acc} prototype)")
    print(f"  Transactions: {pre_txns} ({pre_syn_txns} synthetic, {pre_other_txns} prototype)")
    print(f"  Withdrawals: {pre_wdls}, Complaint-Account Links: {pre_ca}")

    # Step B & C: Fetch cluster and ATM context for generation
    clusters = db.query(LocationCluster).filter(LocationCluster.state == "Delhi").all()
    atms = db.query(ATMLocation).filter(ATMLocation.atm_code.like("ATM-DL-%")).all()
    cluster_dicts = [
        {
            "name": c.cluster_name,
            "zone": c.district,
            "lat": c.center_lat,
            "lon": c.center_lon,
            "id": c.id,
            "risk": c.risk_score if c.risk_score is not None else 0.5,
            "atm_density": c.atm_count if c.atm_count is not None else 4,
        }
        for c in clusters
    ]
    atm_dicts = [
        {
            "atm_code": a.atm_code,
            "bank_name": a.bank_name,
            "cluster_name": [c["name"] for c in cluster_dicts if c["id"] == a.cluster_id][0],
            "id": a.id
        }
        for a in atms
    ]

    # Step D: Generate the ENTIRE new dataset in memory first
    print(f"\n--- D. IN-MEMORY DATASET GENERATION (V2) ---")
    print(f"  Generator seed: {SYNTHETIC_RANDOM_SEED}")
    print(f"  Target complaints: {NUM_COMPLAINTS}, Target accounts: {NUM_ACCOUNTS}")
    gen = DelhiSyntheticDataGenerator(SYNTHETIC_RANDOM_SEED)
    ds = gen.generate_dataset(cluster_dicts, atm_dicts, NUM_COMPLAINTS, NUM_ACCOUNTS)

    # Step E: Run validators against in-memory data
    print("\n--- E. IN-MEMORY VALIDATION PRE-FLIGHT ---")
    n_comp = len(ds["complaints"])
    n_acc = len(ds["accounts"])
    n_ca = len(ds["complaint_accounts"])
    n_tx = len(ds["transactions"])
    n_wd = len(ds["withdrawals"])
    print(f"  Generated Complaints: {n_comp}")
    print(f"  Generated Accounts: {n_acc}")
    print(f"  Generated ComplaintAccounts: {n_ca}")
    print(f"  Generated Transactions: {n_tx}")
    print(f"  Generated Withdrawals: {n_wd}")

    assert n_comp == NUM_COMPLAINTS, f"Complaints count {n_comp} != {NUM_COMPLAINTS}"
    assert n_acc == NUM_ACCOUNTS, f"Accounts count {n_acc} != {NUM_ACCOUNTS}"
    assert n_ca >= n_comp * 2, f"ComplaintAccounts {n_ca} too low"
    assert n_tx >= 40000, f"Transactions count {n_tx} too low"
    assert n_wd >= 1800, f"Withdrawals count {n_wd} too low"

    # Validate referential integrity in memory
    acc_num_set = {a["account_number"] for a in ds["accounts"]}
    comp_num_set = {c["complaint_number"] for c in ds["complaints"]}
    atm_code_set = {a["atm_code"] for a in atm_dicts}

    for tx in ds["transactions"]:
        assert tx["complaint_number"] in comp_num_set, f"Unknown complaint {tx['complaint_number']}"
        assert tx["sender_account_number"] in acc_num_set, f"Unknown sender {tx['sender_account_number']}"
        assert tx["receiver_account_number"] in acc_num_set, f"Unknown receiver {tx['receiver_account_number']}"
        assert tx["amount"] > 0, "Transaction amount must be > 0"

    for w in ds["withdrawals"]:
        assert w["account_number"] in acc_num_set, f"Unknown withdrawal account {w['account_number']}"
        assert w["atm_code"] in atm_code_set, f"Unknown withdrawal atm {w['atm_code']}"
        assert w["amount"] > 0, "Withdrawal amount must be > 0"

    print("  [SUCCESS] All in-memory referential integrity and volume checks PASSED.")

    # Step F: Only if all checks pass: replace generated Delhi synthetic records
    print("\n--- F. ATOMIC DATABASE REPLACEMENT ---")
    syn_acc_ids = [a.id for a in db.query(Account.id).filter(Account.account_number.like(f"{ACCOUNT_PREFIX}%")).all()]
    syn_comp_ids = [c.id for c in db.query(Complaint.id).filter(Complaint.complaint_number.like(f"{COMPLAINT_PREFIX}%")).all()]

    print(f"  Cleaning old synthetic rows ({len(syn_comp_ids)} complaints, {len(syn_acc_ids)} accounts)...")
    if syn_comp_ids:
        # 1. Bank Actions
        db.query(BankAction).filter(BankAction.complaint_id.in_(syn_comp_ids)).delete(synchronize_session=False)

        # 2. Alerts and Alert Outbox
        alert_ids = [a.id for a in db.query(Alert.id).filter(Alert.complaint_id.in_(syn_comp_ids)).all()]
        if alert_ids:
            db.query(NotificationOutbox).filter(NotificationOutbox.alert_id.in_(alert_ids)).delete(synchronize_session=False)
            db.query(Alert).filter(Alert.complaint_id.in_(syn_comp_ids)).delete(synchronize_session=False)

        # 3. Case Handoffs, Evidence Files, Case Notes, Outcome Observations
        db.query(CaseHandoff).filter(CaseHandoff.complaint_id.in_(syn_comp_ids)).delete(synchronize_session=False)
        db.query(EvidenceFile).filter(EvidenceFile.complaint_id.in_(syn_comp_ids)).delete(synchronize_session=False)
        db.query(CaseNote).filter(CaseNote.complaint_id.in_(syn_comp_ids)).delete(synchronize_session=False)
        db.query(OutcomeObservation).filter(OutcomeObservation.complaint_id.in_(syn_comp_ids)).delete(synchronize_session=False)

        # 4. Predictions, Prediction Locations, Prediction Snapshots
        pred_ids = [p.id for p in db.query(Prediction.id).filter(Prediction.complaint_id.in_(syn_comp_ids)).all()]
        if pred_ids:
            db.query(PredictionLocation).filter(PredictionLocation.prediction_id.in_(pred_ids)).delete(synchronize_session=False)
            db.query(PredictionSnapshot).filter(PredictionSnapshot.prediction_id.in_(pred_ids)).delete(synchronize_session=False)
            db.query(Prediction).filter(Prediction.complaint_id.in_(syn_comp_ids)).update({"parent_prediction_id": None}, synchronize_session=False)
            db.query(Prediction).filter(Prediction.complaint_id.in_(syn_comp_ids)).delete(synchronize_session=False)

        # 5. Transactions, Complaint Accounts, Withdrawals
        db.query(Transaction).filter(Transaction.complaint_id.in_(syn_comp_ids)).delete(synchronize_session=False)
        db.query(ComplaintAccount).filter(ComplaintAccount.complaint_id.in_(syn_comp_ids)).delete(synchronize_session=False)
        db.query(Withdrawal).filter(Withdrawal.complaint_id.in_(syn_comp_ids)).delete(synchronize_session=False)

        # 6. Complaints
        db.query(Complaint).filter(Complaint.id.in_(syn_comp_ids)).delete(synchronize_session=False)

    if syn_acc_ids:
        # Delete any remaining transactions/withdrawals/accounts on synthetic accounts
        db.query(Transaction).filter(
            (Transaction.sender_account_id.in_(syn_acc_ids)) | (Transaction.receiver_account_id.in_(syn_acc_ids))
        ).delete(synchronize_session=False)
        db.query(Withdrawal).filter(Withdrawal.account_id.in_(syn_acc_ids)).delete(synchronize_session=False)
        db.query(ComplaintAccount).filter(ComplaintAccount.account_id.in_(syn_acc_ids)).delete(synchronize_session=False)
        db.query(Account).filter(Account.id.in_(syn_acc_ids)).delete(synchronize_session=False)
            
    db.flush()

    # Batch insert Accounts
    print(f"  Inserting {len(ds['accounts'])} new accounts...")
    acc_objs = [Account(**acc) for acc in ds["accounts"]]
    BATCH_SIZE = 1000
    for i in range(0, len(acc_objs), BATCH_SIZE):
        db.add_all(acc_objs[i:i + BATCH_SIZE])
        db.flush()

    acc_map = dict(db.query(Account.account_number, Account.id).filter(Account.account_number.like(f"{ACCOUNT_PREFIX}%")).all())

    # Batch insert Complaints
    print(f"  Inserting {len(ds['complaints'])} new complaints...")
    comp_objs = [Complaint(**comp) for comp in ds["complaints"]]
    for i in range(0, len(comp_objs), BATCH_SIZE):
        db.add_all(comp_objs[i:i + BATCH_SIZE])
        db.flush()

    comp_map = dict(db.query(Complaint.complaint_number, Complaint.id).filter(Complaint.complaint_number.like(f"{COMPLAINT_PREFIX}%")).all())
    atm_map = dict(db.query(ATMLocation.atm_code, ATMLocation.id).filter(ATMLocation.atm_code.like("ATM-DL-%")).all())

    # Batch insert ComplaintAccounts
    print(f"  Inserting {len(ds['complaint_accounts'])} new complaint_accounts...")
    ca_objs = []
    for ca in ds["complaint_accounts"]:
        c_id = comp_map.get(ca["complaint_number"])
        a_id = acc_map.get(ca["account_number"])
        if c_id and a_id:
            ca_objs.append(ComplaintAccount(complaint_id=c_id, account_id=a_id, association_type=ca["association_type"]))

    for i in range(0, len(ca_objs), BATCH_SIZE):
        db.add_all(ca_objs[i:i + BATCH_SIZE])
        db.flush()

    # Batch insert Transactions
    print(f"  Inserting {len(ds['transactions'])} new transactions...")
    tx_objs = []
    for tx in ds["transactions"]:
        c_id = comp_map.get(tx["complaint_number"])
        s_id = acc_map.get(tx["sender_account_number"])
        r_id = acc_map.get(tx["receiver_account_number"])
        if c_id and s_id and r_id:
            tx_objs.append(Transaction(
                transaction_ref=tx["transaction_ref"],
                complaint_id=c_id,
                sender_account_id=s_id,
                receiver_account_id=r_id,
                amount=tx["amount"],
                payment_channel=tx["payment_channel"],
                timestamp=tx["timestamp"],
                hop_number=tx["hop_number"],
                status=tx["status"],
                suspicious_flag=tx["suspicious_flag"]
            ))

    for i in range(0, len(tx_objs), BATCH_SIZE):
        db.add_all(tx_objs[i:i + BATCH_SIZE])
        db.flush()

    # Batch insert Withdrawals
    print(f"  Inserting {len(ds['withdrawals'])} new withdrawals...")
    w_objs = []
    for w in ds["withdrawals"]:
        atm_id = atm_map.get(w["atm_code"])
        a_id = acc_map.get(w["account_number"])
        c_id = comp_map.get(w.get("complaint_number"))
        if atm_id and a_id:
            w_objs.append(Withdrawal(
                withdrawal_ref=w.get("withdrawal_ref"),
                complaint_id=c_id,
                atm_id=atm_id,
                account_id=a_id,
                amount=w["amount"],
                timestamp=w["timestamp"],
                success=w["success"],
                camera_flagged=w["camera_flagged"]
            ))

    for i in range(0, len(w_objs), BATCH_SIZE):
        db.add_all(w_objs[i:i + BATCH_SIZE])
        db.flush()

    db.commit()
    print(f"  Database commit complete in {time.time() - t0:.2f}s")

    # Post-generation counts and prototype verification
    print("\n--- POST-GENERATION DATABASE COUNTS & PROTOTYPE VERIFICATION ---")
    post_users = db.query(User).count()
    post_orgs = db.query(Organization).count()
    post_cmp1042 = db.query(Complaint).filter(Complaint.complaint_number == "CMP-1042").count()
    post_delhi_comp = db.query(Complaint).filter(Complaint.complaint_number.like(f"{COMPLAINT_PREFIX}%")).count()
    post_other_comp = db.query(Complaint).filter(~Complaint.complaint_number.like(f"{COMPLAINT_PREFIX}%")).count()

    post_syn_acc = db.query(Account).filter(Account.account_number.like(f"{ACCOUNT_PREFIX}%")).count()
    post_other_acc = db.query(Account).filter(~Account.account_number.like(f"{ACCOUNT_PREFIX}%")).count()

    post_syn_tx = db.query(Transaction).filter(Transaction.transaction_ref.like(f"{TRANSACTION_PREFIX}%")).count()
    post_other_tx = db.query(Transaction).filter(~Transaction.transaction_ref.like(f"{TRANSACTION_PREFIX}%")).count()

    post_wdls = db.query(Withdrawal).count()
    post_ca = db.query(ComplaintAccount).count()

    print(f"  Users: {post_users} (Expected: {pre_users}) -> {'MATCH' if post_users == pre_users else 'MISMATCH'}")
    print(f"  Orgs: {post_orgs} (Expected: {pre_orgs}) -> {'MATCH' if post_orgs == pre_orgs else 'MISMATCH'}")
    print(f"  CMP-1042: {post_cmp1042} (Expected: 0) -> {'PURGED' if post_cmp1042 == 0 else 'WARNING_PRESENT'}")
    print(f"  Prototype Complaints: {post_other_comp} (Expected: {pre_other_comp}) -> {'MATCH' if post_other_comp == pre_other_comp else 'MISMATCH'}")
    print(f"  Prototype Accounts: {post_other_acc} (Expected: {pre_other_acc}) -> {'MATCH' if post_other_acc == pre_other_acc else 'MISMATCH'}")
    print(f"  Prototype Transactions: {post_other_tx} (Expected: {pre_other_txns}) -> {'MATCH' if post_other_tx == pre_other_txns else 'MISMATCH'}")
    print(f"  Delhi Synthetic Complaints: {post_delhi_comp}")
    print(f"  Delhi Synthetic Accounts: {post_syn_acc}")
    print(f"  Delhi Synthetic Transactions: {post_syn_tx}")
    print(f"  Delhi Withdrawals: {post_wdls}")
    print(f"  Complaint-Account Links: {post_ca}")

    db.close()
    print("======================================================================")
    print("SYNTHETIC DATASET V2 RESEEDING COMPLETE")
    print("======================================================================")

if __name__ == "__main__":
    run()
