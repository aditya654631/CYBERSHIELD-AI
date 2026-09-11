"""
CyberShield AI — Master Database Seeder
Phase 1 Step 4: Idempotent, Category-Specific Seeding with Delhi Operational Dataset
"""

import time
import datetime
import random
from decimal import Decimal
from typing import Dict, Any, List, Tuple
from sqlalchemy.orm import Session

from backend.app.models.db import SessionLocal, engine, Base
from backend.app.models.models import (
    Organization, User, LocationCluster, ATMLocation,
    Complaint, Account, ComplaintAccount, Transaction,
    Prediction, PredictionLocation, Alert, AuditLog, Withdrawal
)
from backend.app.auth.security import get_password_hash
from database.seed.seed_config import (
    SYNTHETIC_RANDOM_SEED, COMPLAINT_PREFIX, ACCOUNT_PREFIX,
    NUM_COMPLAINTS, NUM_ACCOUNTS
)
from database.seed.delhi_geography import DELHI_CLUSTERS_DATA, generate_delhi_atms
from database.seed.synthetic_generator import DelhiSyntheticDataGenerator

def seed_auth_and_organizations(db: Session) -> None:
    """Seeds baseline organizations and administrative users if not already present."""
    if db.query(Organization).first() and db.query(User).first():
        return

    print("[Seed] Seeding baseline organizations and administrative users...")
    i4c_org = Organization(name="National Cybercrime Coordination Centre (I4C)", org_type="I4C", state="New Delhi", district="Central")
    mp_state_lea = Organization(name="Madhya Pradesh State Cyber Police Headquarters", org_type="LEA", state="Madhya Pradesh", district="Bhopal")
    indore_lea = Organization(name="Indore District Cyber Cell", org_type="LEA", state="Madhya Pradesh", district="Indore")
    sbi_bank = Organization(name="State Bank of India - Fraud Risk Management Unit", org_type="BANK", state="Maharashtra", district="Mumbai")
    mha_audit = Organization(name="Ministry of Home Affairs Oversight & Compliance", org_type="I4C", state="New Delhi", district="Central")

    db.add_all([i4c_org, mp_state_lea, indore_lea, sbi_bank, mha_audit])
    db.flush()

    users = [
        User(
            email="admin@cybershield.gov.in",
            hashed_password=get_password_hash("CyberAdmin@2026"),
            full_name="Dr. Vikramaditya Sen",
            role="I4C_ADMIN",
            badge_number="I4C-DIR-001",
            organization_id=i4c_org.id
        ),
        User(
            email="state.lea@mp.police.gov.in",
            hashed_password=get_password_hash("StateLea@2026"),
            full_name="SP Anand Shekhawat, IPS",
            role="STATE_LEA",
            badge_number="MP-CYBER-09",
            organization_id=mp_state_lea.id
        ),
        User(
            email="district.lea@indore.police.gov.in",
            hashed_password=get_password_hash("IndoreLea@2026"),
            full_name="Inspector Rajesh Verma",
            role="DISTRICT_LEA",
            badge_number="IND-CY-441",
            organization_id=indore_lea.id
        ),
        User(
            email="officer@sbi.co.in",
            hashed_password=get_password_hash("BankOfficer@2026"),
            full_name="Sunita Deshmukh",
            role="BANK_OFFICER",
            badge_number="SBI-FRMU-88",
            organization_id=sbi_bank.id
        ),
        User(
            email="analyst@cybershield.gov.in",
            hashed_password=get_password_hash("Analyst@2026"),
            full_name="Pooja Kulkarni",
            role="ANALYST",
            badge_number="CS-AN-102",
            organization_id=i4c_org.id
        ),
        User(
            email="auditor@mha.gov.in",
            hashed_password=get_password_hash("Auditor@2026"),
            full_name="Col. Sanjeev Nair (Retd.)",
            role="AUDITOR",
            badge_number="MHA-AUD-07",
            organization_id=mha_audit.id
        )
    ]
    db.add_all(users)
    db.flush()

def seed_demo_case_cmp1042(db: Session) -> None:
    """Preserves the CMP-1042 deterministic demo case and historical prototype data."""
    if db.query(Complaint).filter(Complaint.complaint_number == "CMP-1042").first():
        return

    print("[Seed] Seeding CMP-1042 demo case and prototype clusters...")
    clusters = [
        LocationCluster(cluster_name="Vijay Nagar, Indore", city="Indore", district="Indore", state="Madhya Pradesh", center_lat=22.7533, center_lon=75.8937, radius_km=1.8, historical_fraud_count=19, atm_count=12, risk_score=0.87),
        LocationCluster(cluster_name="Palasia, Indore", city="Indore", district="Indore", state="Madhya Pradesh", center_lat=22.7244, center_lon=75.8839, radius_km=2.1, historical_fraud_count=11, atm_count=9, risk_score=0.61),
        LocationCluster(cluster_name="Rau, Indore", city="Indore", district="Indore", state="Madhya Pradesh", center_lat=22.6288, center_lon=75.8080, radius_km=3.0, historical_fraud_count=4, atm_count=5, risk_score=0.34),
        LocationCluster(cluster_name="MP Nagar, Bhopal", city="Bhopal", district="Bhopal", state="Madhya Pradesh", center_lat=23.2332, center_lon=77.4343, radius_km=2.4, historical_fraud_count=15, atm_count=14, risk_score=0.74),
        LocationCluster(cluster_name="New Market, Bhopal", city="Bhopal", district="Bhopal", state="Madhya Pradesh", center_lat=23.2363, center_lon=77.4013, radius_km=2.0, historical_fraud_count=9, atm_count=8, risk_score=0.58),
        LocationCluster(cluster_name="Freeganj, Ujjain", city="Ujjain", district="Ujjain", state="Madhya Pradesh", center_lat=23.1824, center_lon=75.7892, radius_km=2.2, historical_fraud_count=7, atm_count=7, risk_score=0.65)
    ]
    db.add_all(clusters)
    db.flush()

    atms = [
        ATMLocation(atm_code="ATM-SBI-VN01", bank_name="State Bank of India", address="AB Road, Scheme 54, Vijay Nagar", city="Indore", district="Indore", latitude=22.7540, longitude=75.8942, cluster_id=clusters[0].id, risk_rating="CRITICAL"),
        ATMLocation(atm_code="ATM-HDFC-VN02", bank_name="HDFC Bank", address="Near C21 Mall, Vijay Nagar", city="Indore", district="Indore", latitude=22.7521, longitude=75.8928, cluster_id=clusters[0].id, risk_rating="CRITICAL"),
        ATMLocation(atm_code="ATM-PNB-VN03", bank_name="Punjab National Bank", address="Sayaji Circle, Vijay Nagar", city="Indore", district="Indore", latitude=22.7552, longitude=75.8955, cluster_id=clusters[0].id, risk_rating="CRITICAL"),
        ATMLocation(atm_code="ATM-ICICI-VN04", bank_name="ICICI Bank", address="Bhamori, Vijay Nagar", city="Indore", district="Indore", latitude=22.7510, longitude=75.8910, cluster_id=clusters[0].id, risk_rating="HIGH"),
        ATMLocation(atm_code="ATM-AXIS-PL01", bank_name="Axis Bank", address="Old Palasia Main Road", city="Indore", district="Indore", latitude=22.7235, longitude=75.8825, cluster_id=clusters[1].id, risk_rating="HIGH"),
        ATMLocation(atm_code="ATM-BOB-PL02", bank_name="Bank of Baroda", address="Industry House, Palasia", city="Indore", district="Indore", latitude=22.7258, longitude=75.8850, cluster_id=clusters[1].id, risk_rating="MEDIUM"),
        ATMLocation(atm_code="ATM-SBI-RA01", bank_name="State Bank of India", address="Rau Pithampur Road", city="Indore", district="Indore", latitude=22.6275, longitude=75.8070, cluster_id=clusters[2].id, risk_rating="MEDIUM"),
        ATMLocation(atm_code="ATM-SBI-MP01", bank_name="State Bank of India", address="Zone I, MP Nagar", city="Bhopal", district="Bhopal", latitude=23.2340, longitude=77.4330, cluster_id=clusters[3].id, risk_rating="HIGH"),
        ATMLocation(atm_code="ATM-HDFC-MP02", bank_name="HDFC Bank", address="Zone II, MP Nagar", city="Bhopal", district="Bhopal", latitude=23.2325, longitude=77.4360, cluster_id=clusters[3].id, risk_rating="HIGH"),
        ATMLocation(atm_code="ATM-ICICI-UJ01", bank_name="ICICI Bank", address="Tower Chowk, Freeganj", city="Ujjain", district="Ujjain", latitude=23.1830, longitude=75.7905, cluster_id=clusters[5].id, risk_rating="HIGH")
    ]
    db.add_all(atms)
    db.flush()

    now = datetime.datetime.utcnow()
    cmp1042 = Complaint(
        complaint_number="CMP-1042",
        fraud_type="Investment Scam",
        amount=Decimal("125000.00"),
        victim_name="Rajesh Sharma",
        victim_phone="+91 98260 41239",
        victim_location="Arera Colony, Bhopal, Madhya Pradesh",
        state="Madhya Pradesh",
        district="Bhopal",
        payment_channel="UPI",
        reported_at=now - datetime.timedelta(hours=1, minutes=15),
        incident_time=now - datetime.timedelta(hours=1, minutes=45),
        risk_level="CRITICAL",
        risk_score=0.87,
        prediction_status="COMPLETED",
        case_status="ACTIVE"
    )
    db.add(cmp1042)
    db.flush()

    acc_victim = Account(account_number="309100029182", masked_account="ACC••••9012", bank_name="State Bank of India", branch="Bhopal Main Branch", ifsc="SBIN0001056", holder_name="Rajesh Sharma (Victim)", account_type="SAVINGS", risk_score=0.05, is_mule=False)
    acc_a = Account(account_number="5010049283481", masked_account="ACC••••3481", bank_name="HDFC Bank", branch="Indore Layering Node", ifsc="HDFC0000241", holder_name="Alpha Tech Services (Intermediary)", account_type="CURRENT", risk_score=0.68, is_mule=True, flag_reason="Rapid fund dispersion within 4 minutes")
    acc_b = Account(account_number="0039019287104", masked_account="ACC••••7104", bank_name="ICICI Bank", branch="Indore Scheme 54", ifsc="ICIC0000039", holder_name="Sunil Mehra (Layer 2)", account_type="SAVINGS", risk_score=0.74, is_mule=True, flag_reason="Mule account linked to known ring")
    acc_c = Account(account_number="91801004925529", masked_account="ACC••••5529", bank_name="Axis Bank", branch="Indore South Tukoganj", ifsc="UTIB0000142", holder_name="Vikas Solanki (Layer 2)", account_type="SAVINGS", risk_score=0.79, is_mule=True, flag_reason="Multiple recent P2P UPI transfers")
    acc_mule_d = Account(account_number="12440021008129", masked_account="ACC••••8129", bank_name="Punjab National Bank", branch="Vijay Nagar Commercial", ifsc="PUNB0124400", holder_name="Deepak Kumar (Known ATM Cashier)", account_type="SAVINGS", risk_score=0.94, is_mule=True, flag_reason="Repeated ATM cash extractions in Vijay Nagar cluster")
    acc_mule_e = Account(account_number="652109846291", masked_account="ACC••••6291", bank_name="Kotak Mahindra Bank", branch="Indore AB Road", ifsc="KKBK0000721", holder_name="Rahul Verma (Terminal Mule)", account_type="SAVINGS", risk_score=0.91, is_mule=True, flag_reason="High cash withdrawal velocity record")
    db.add_all([acc_victim, acc_a, acc_b, acc_c, acc_mule_d, acc_mule_e])
    db.flush()

    # Link accounts in complaint_accounts
    for acc, role in [(acc_victim, "VICTIM"), (acc_a, "INTERMEDIARY"), (acc_b, "INTERMEDIARY"), (acc_c, "INTERMEDIARY"), (acc_mule_d, "MULE"), (acc_mule_e, "MULE")]:
        db.add(ComplaintAccount(complaint_id=cmp1042.id, account_id=acc.id, association_type=role))

    txs = [
        Transaction(transaction_ref="TXN-UPI-9012481", complaint_id=cmp1042.id, sender_account_id=acc_victim.id, receiver_account_id=acc_a.id, amount=Decimal("125000.00"), payment_channel="UPI (Immediate)", timestamp=now - datetime.timedelta(minutes=75), hop_number=1, status="COMPLETED", suspicious_flag=True),
        Transaction(transaction_ref="TXN-IMPS-3487104", complaint_id=cmp1042.id, sender_account_id=acc_a.id, receiver_account_id=acc_b.id, amount=Decimal("75000.00"), payment_channel="IMPS Rapid", timestamp=now - datetime.timedelta(minutes=68), hop_number=2, status="COMPLETED", suspicious_flag=True),
        Transaction(transaction_ref="TXN-IMPS-3485529", complaint_id=cmp1042.id, sender_account_id=acc_a.id, receiver_account_id=acc_c.id, amount=Decimal("50000.00"), payment_channel="IMPS Rapid", timestamp=now - datetime.timedelta(minutes=67), hop_number=2, status="COMPLETED", suspicious_flag=True),
        Transaction(transaction_ref="TXN-NEFT-7108129", complaint_id=cmp1042.id, sender_account_id=acc_b.id, receiver_account_id=acc_mule_d.id, amount=Decimal("75000.00"), payment_channel="NEFT Rapid", timestamp=now - datetime.timedelta(minutes=55), hop_number=3, status="COMPLETED", suspicious_flag=True),
        Transaction(transaction_ref="TXN-UPI-5526291", complaint_id=cmp1042.id, sender_account_id=acc_c.id, receiver_account_id=acc_mule_e.id, amount=Decimal("50000.00"), payment_channel="UPI P2P", timestamp=now - datetime.timedelta(minutes=52), hop_number=3, status="COMPLETED", suspicious_flag=True)
    ]
    db.add_all(txs)
    db.flush()

    pred_1042 = Prediction(
        complaint_id=cmp1042.id,
        model_version="CyberShield-XGB-v1.4 (Hybrid Ensemble)",
        predicted_window_start=now + datetime.timedelta(hours=2),
        predicted_window_end=now + datetime.timedelta(hours=4),
        window_label="Next 2–4 Hours",
        primary_cluster_id=clusters[0].id,
        risk_score=0.87,
        risk_level="CRITICAL",
        confidence_score=0.92,
        ml_score=0.88,
        graph_score=0.85,
        geo_score=0.84,
        temporal_score=0.80,
        intervention_priority=94,
        why_explanation="Beneficiary mule network shares historical relationships with accounts previously associated with cash withdrawals in this geographic cluster.",
        created_at=now - datetime.timedelta(minutes=45)
    )
    db.add(pred_1042)
    db.flush()

    pred_locs = [
        PredictionLocation(prediction_id=pred_1042.id, cluster_id=clusters[0].id, location_name="Vijay Nagar, Indore", rank=1, probability=0.87, risk_level="CRITICAL", distance_km=186.4, reasoning="High Mule-Network Similarity & Recent ATM Cashier Activity", latitude=22.7533, longitude=75.8937),
        PredictionLocation(prediction_id=pred_1042.id, cluster_id=clusters[1].id, location_name="Palasia, Indore", rank=2, probability=0.61, risk_level="HIGH", distance_km=189.1, reasoning="Secondary ATM Cluster linked to Mule B layering account", latitude=22.7244, longitude=75.8839),
        PredictionLocation(prediction_id=pred_1042.id, cluster_id=clusters[2].id, location_name="Rau, Indore", rank=3, probability=0.34, risk_level="MEDIUM", distance_km=198.7, reasoning="Outlying highway ATM node with low historical frequency", latitude=22.6288, longitude=75.8080)
    ]
    db.add_all(pred_locs)

    alert_1042 = Alert(
        complaint_id=cmp1042.id,
        prediction_id=pred_1042.id,
        title="CRITICAL CASH-OUT IMMINENT: Vijay Nagar, Indore (CMP-1042)",
        severity="CRITICAL",
        location_name="Vijay Nagar, Indore",
        risk_score=0.87,
        expected_window="Next 2–4 Hours",
        amount_at_risk=Decimal("125000.00"),
        status="NEW",
        created_at=now - datetime.timedelta(minutes=40)
    )
    db.add(alert_1042)

    db.add(AuditLog(
        officer_name="System Supervisor",
        role="I4C_ADMIN",
        action="SYSTEM_INITIALIZED",
        case_number="SYSTEM",
        details="CyberShield AI National Predictive Engine initialized with active LEA nodes."
    ))
    db.flush()

def seed_delhi_geography(db: Session) -> Tuple[List[LocationCluster], List[ATMLocation]]:
    """Idempotently seeds 60 Delhi location clusters and 240 context ATMs."""
    existing_delhi_clusters = db.query(LocationCluster).filter(LocationCluster.state == "Delhi").all()
    if existing_delhi_clusters:
        delhi_atms = db.query(ATMLocation).filter(ATMLocation.state == "Delhi").all()
        return existing_delhi_clusters, delhi_atms

    print("[Seed] Seeding 60 Delhi location clusters and 240 synthetic context ATMs...")
    clusters = []
    for c_data in DELHI_CLUSTERS_DATA:
        cl = LocationCluster(
            cluster_name=c_data["name"],
            city="Delhi",
            district=c_data["zone"],
            state="Delhi",
            center_lat=c_data["lat"],
            center_lon=c_data["lon"],
            radius_km=c_data["radius"],
            historical_fraud_count=c_data["fraud_count"],
            atm_count=4,
            risk_score=c_data["risk"]
        )
        clusters.append(cl)

    db.add_all(clusters)
    db.flush()

    # Generate 240 ATMs (4 per cluster)
    generated_atms = generate_delhi_atms(DELHI_CLUSTERS_DATA)
    cluster_map = {c.cluster_name: c.id for c in clusters}

    atm_objects = []
    for a_data in generated_atms:
        cl_id = cluster_map.get(a_data["cluster_name"])
        atm = ATMLocation(
            atm_code=a_data["atm_code"],
            bank_name=a_data["bank_name"],
            address=a_data["address"],
            city="Delhi",
            district=a_data["district"],
            state="Delhi",
            latitude=a_data["latitude"],
            longitude=a_data["longitude"],
            cash_available=a_data["cash_available"],
            risk_rating=a_data["risk_rating"],
            cluster_id=cl_id
        )
        atm_objects.append(atm)

    db.add_all(atm_objects)
    db.flush()
    return clusters, atm_objects

def seed_delhi_operational_dataset(db: Session, clusters: List[LocationCluster], atms: List[ATMLocation]) -> None:
    """Idempotently seeds the full synthetic Delhi operational dataset."""
    existing_delhi_complaint = db.query(Complaint).filter(Complaint.complaint_number.like(f"{COMPLAINT_PREFIX}%")).first()
    if existing_delhi_complaint:
        print("[Seed] Delhi synthetic operational dataset already seeded. Skipping generation.")
        return

    print(f"[Seed] Generating deterministic Delhi operational dataset (seed={SYNTHETIC_RANDOM_SEED})...")
    t0 = time.time()
    
    cluster_dicts = [
        {"name": c.cluster_name, "zone": c.district, "lat": c.center_lat, "lon": c.center_lon, "id": c.id}
        for c in clusters
    ]
    atm_dicts = [
        {"atm_code": a.atm_code, "bank_name": a.bank_name, "cluster_name": [c["name"] for c in cluster_dicts if c["id"] == a.cluster_id][0], "id": a.id}
        for a in atms
    ]

    generator = DelhiSyntheticDataGenerator(SYNTHETIC_RANDOM_SEED)
    dataset = generator.generate_dataset(cluster_dicts, atm_dicts, NUM_COMPLAINTS, NUM_ACCOUNTS)

    # 1. Batch insert Accounts (6,000)
    print(f"[Seed] Batch inserting {len(dataset['accounts'])} accounts...")
    account_objs = [Account(**acc) for acc in dataset["accounts"]]
    BATCH_SIZE = 1000
    for i in range(0, len(account_objs), BATCH_SIZE):
        db.add_all(account_objs[i:i + BATCH_SIZE])
        db.flush()

    # Build account_number -> id mapping
    acc_map = dict(db.query(Account.account_number, Account.id).filter(Account.account_number.like(f"{ACCOUNT_PREFIX}%")).all())

    # 2. Batch insert Complaints (3,000)
    print(f"[Seed] Batch inserting {len(dataset['complaints'])} complaints...")
    complaint_objs = [Complaint(**comp) for comp in dataset["complaints"]]
    for i in range(0, len(complaint_objs), BATCH_SIZE):
        db.add_all(complaint_objs[i:i + BATCH_SIZE])
        db.flush()

    # Build complaint_number -> id mapping
    comp_map = dict(db.query(Complaint.complaint_number, Complaint.id).filter(Complaint.complaint_number.like(f"{COMPLAINT_PREFIX}%")).all())
    atm_map = dict(db.query(ATMLocation.atm_code, ATMLocation.id).filter(ATMLocation.atm_code.like("ATM-DL-%")).all())

    # 3. Batch insert ComplaintAccounts (~35,000)
    print(f"[Seed] Batch inserting {len(dataset['complaint_accounts'])} complaint-account associations...")
    ca_objs = []
    for ca in dataset["complaint_accounts"]:
        c_id = comp_map.get(ca["complaint_number"])
        a_id = acc_map.get(ca["account_number"])
        if c_id and a_id:
            ca_objs.append(ComplaintAccount(
                complaint_id=c_id,
                account_id=a_id,
                association_type=ca["association_type"]
            ))
    for i in range(0, len(ca_objs), BATCH_SIZE * 2):
        db.add_all(ca_objs[i:i + BATCH_SIZE * 2])
        db.flush()

    # 4. Batch insert Transactions (~50,000)
    print(f"[Seed] Batch inserting {len(dataset['transactions'])} multi-hop transactions...")
    tx_objs = []
    for tx in dataset["transactions"]:
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
    for i in range(0, len(tx_objs), BATCH_SIZE * 2):
        db.add_all(tx_objs[i:i + BATCH_SIZE * 2])
        db.flush()

    # 5. Batch insert Withdrawals (~2,100)
    print(f"[Seed] Batch inserting {len(dataset['withdrawals'])} cash-out withdrawals...")
    w_objs = []
    for w in dataset["withdrawals"]:
        a_id = atm_map.get(w["atm_code"])
        acc_id = acc_map.get(w["account_number"])
        if a_id and acc_id:
            w_objs.append(Withdrawal(
                atm_id=a_id,
                account_id=acc_id,
                amount=w["amount"],
                timestamp=w["timestamp"],
                success=w["success"],
                camera_flagged=w["camera_flagged"]
            ))
    for i in range(0, len(w_objs), BATCH_SIZE):
        db.add_all(w_objs[i:i + BATCH_SIZE])
        db.flush()

    elapsed = time.time() - t0
    print(f"[Seed] Successfully generated and committed Delhi synthetic operational dataset in {elapsed:.2f}s!")

def seed_database(db: Session) -> None:
    """
    Main seed orchestrator.
    Idempotently executes all 4 seeding phases:
    1. Authentication and Organizations
    2. CMP-1042 Prototype Demo Case
    3. Delhi Geography (60 clusters, 240 ATMs)
    4. Delhi Operational Dataset (3,000 complaints, 6,000 accounts, ~50,000 transactions, ~2,100 withdrawals)
    """
    t_start = time.time()
    print("[Seed] CyberShield AI idempotent database seeding starting...")

    seed_auth_and_organizations(db)
    seed_demo_case_cmp1042(db)
    clusters, atms = seed_delhi_geography(db)
    seed_delhi_operational_dataset(db, clusters, atms)

    db.commit()
    t_total = time.time() - t_start
    print(f"[Seed] Database seeding verification complete in {t_total:.2f}s.")

if __name__ == "__main__":
    Base.metadata.create_all(bind=engine)
    db_session = SessionLocal()
    try:
        seed_database(db_session)
    finally:
        db_session.close()
