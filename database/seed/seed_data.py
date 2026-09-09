import datetime
import random
from sqlalchemy.orm import Session
from backend.app.models.db import SessionLocal, engine, Base
from backend.app.models.models import (
    Organization, User, LocationCluster, ATMLocation,
    Complaint, Account, Transaction, Prediction, PredictionLocation, Alert, AuditLog
)
from backend.app.auth.security import get_password_hash

def seed_database(db: Session):
    print("[Seed] Initializing CyberShield AI database...")

    # Check if already seeded
    if db.query(User).first():
        print("[Seed] Database already contains records. Skipping initial seeding.")
        return

    # 1. Organizations
    i4c_org = Organization(name="National Cybercrime Coordination Centre (I4C)", org_type="I4C", state="New Delhi", district="Central")
    mp_state_lea = Organization(name="Madhya Pradesh State Cyber Police Headquarters", org_type="LEA", state="Madhya Pradesh", district="Bhopal")
    indore_lea = Organization(name="Indore District Cyber Cell", org_type="LEA", state="Madhya Pradesh", district="Indore")
    sbi_bank = Organization(name="State Bank of India - Fraud Risk Management Unit", org_type="BANK", state="Maharashtra", district="Mumbai")
    mha_audit = Organization(name="Ministry of Home Affairs Oversight & Compliance", org_type="I4C", state="New Delhi", district="Central")

    db.add_all([i4c_org, mp_state_lea, indore_lea, sbi_bank, mha_audit])
    db.flush()

    # 2. Users (All required roles seeded)
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

    # 3. Location Clusters (Madhya Pradesh focus: Indore, Bhopal, Ujjain, Rau, etc.)
    clusters = [
        LocationCluster(
            cluster_name="Vijay Nagar, Indore",
            city="Indore",
            district="Indore",
            state="Madhya Pradesh",
            center_lat=22.7533,
            center_lon=75.8937,
            radius_km=1.8,
            historical_fraud_count=19,
            atm_count=12,
            risk_score=0.87
        ),
        LocationCluster(
            cluster_name="Palasia, Indore",
            city="Indore",
            district="Indore",
            state="Madhya Pradesh",
            center_lat=22.7244,
            center_lon=75.8839,
            radius_km=2.1,
            historical_fraud_count=11,
            atm_count=9,
            risk_score=0.61
        ),
        LocationCluster(
            cluster_name="Rau, Indore",
            city="Indore",
            district="Indore",
            state="Madhya Pradesh",
            center_lat=22.6288,
            center_lon=75.8080,
            radius_km=3.0,
            historical_fraud_count=4,
            atm_count=5,
            risk_score=0.34
        ),
        LocationCluster(
            cluster_name="MP Nagar, Bhopal",
            city="Bhopal",
            district="Bhopal",
            state="Madhya Pradesh",
            center_lat=23.2332,
            center_lon=77.4343,
            radius_km=2.4,
            historical_fraud_count=15,
            atm_count=14,
            risk_score=0.74
        ),
        LocationCluster(
            cluster_name="New Market, Bhopal",
            city="Bhopal",
            district="Bhopal",
            state="Madhya Pradesh",
            center_lat=23.2363,
            center_lon=77.4013,
            radius_km=2.0,
            historical_fraud_count=9,
            atm_count=8,
            risk_score=0.58
        ),
        LocationCluster(
            cluster_name="Freeganj, Ujjain",
            city="Ujjain",
            district="Ujjain",
            state="Madhya Pradesh",
            center_lat=23.1824,
            center_lon=75.7892,
            radius_km=2.2,
            historical_fraud_count=7,
            atm_count=7,
            risk_score=0.65
        )
    ]
    db.add_all(clusters)
    db.flush()

    # 4. ATMs in key clusters
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

    # 5. Core Demo Case: CMP-1042 (Seeded exactly as specified)
    # Investment Scam, ₹1,25,000, Bhopal, Madhya Pradesh, UPI, 19:42
    cmp1042 = Complaint(
        complaint_number="CMP-1042",
        fraud_type="Investment Scam",
        amount=125000.0,
        victim_name="Rajesh Sharma",
        victim_phone="+91 98260 41239",
        victim_location="Arera Colony, Bhopal, Madhya Pradesh",
        state="Madhya Pradesh",
        district="Bhopal",
        payment_channel="UPI",
        reported_at=datetime.datetime.utcnow() - datetime.timedelta(hours=1, minutes=15),
        incident_time=datetime.datetime.utcnow() - datetime.timedelta(hours=1, minutes=45),
        risk_level="CRITICAL",
        risk_score=0.87,
        prediction_status="COMPLETED",
        case_status="ACTIVE"
    )
    db.add(cmp1042)
    db.flush()

    # Seed Accounts for CMP-1042
    acc_victim = Account(
        account_number="309100029182",
        masked_account="ACC••••9012",
        bank_name="State Bank of India",
        branch="Bhopal Main Branch",
        ifsc="SBIN0001056",
        holder_name="Rajesh Sharma (Victim)",
        account_type="SAVINGS",
        risk_score=0.05,
        is_mule=False
    )
    acc_a = Account(
        account_number="5010049283481",
        masked_account="ACC••••3481",
        bank_name="HDFC Bank",
        branch="Indore Layering Node",
        ifsc="HDFC0000241",
        holder_name="Alpha Tech Services (Intermediary)",
        account_type="CURRENT",
        risk_score=0.68,
        is_mule=True,
        flag_reason="Rapid fund dispersion within 4 minutes"
    )
    acc_b = Account(
        account_number="0039019287104",
        masked_account="ACC••••7104",
        bank_name="ICICI Bank",
        branch="Indore Scheme 54",
        ifsc="ICIC0000039",
        holder_name="Sunil Mehra (Layer 2)",
        account_type="SAVINGS",
        risk_score=0.74,
        is_mule=True,
        flag_reason="Mule account linked to known ring"
    )
    acc_c = Account(
        account_number="91801004925529",
        masked_account="ACC••••5529",
        bank_name="Axis Bank",
        branch="Indore South Tukoganj",
        ifsc="UTIB0000142",
        holder_name="Vikas Solanki (Layer 2)",
        account_type="SAVINGS",
        risk_score=0.79,
        is_mule=True,
        flag_reason="Multiple recent P2P UPI transfers"
    )
    acc_mule_d = Account(
        account_number="12440021008129",
        masked_account="ACC••••8129",
        bank_name="Punjab National Bank",
        branch="Vijay Nagar Commercial",
        ifsc="PUNB0124400",
        holder_name="Deepak Kumar (Known ATM Cashier)",
        account_type="SAVINGS",
        risk_score=0.94,
        is_mule=True,
        flag_reason="Repeated ATM cash extractions in Vijay Nagar cluster"
    )
    acc_mule_e = Account(
        account_number="652109846291",
        masked_account="ACC••••6291",
        bank_name="Kotak Mahindra Bank",
        branch="Indore AB Road",
        ifsc="KKBK0000721",
        holder_name="Rahul Verma (Terminal Mule)",
        account_type="SAVINGS",
        risk_score=0.91,
        is_mule=True,
        flag_reason="High cash withdrawal velocity record"
    )
    db.add_all([acc_victim, acc_a, acc_b, acc_c, acc_mule_d, acc_mule_e])
    db.flush()

    # Seed Transactions for CMP-1042
    now = datetime.datetime.utcnow()
    txs = [
        Transaction(
            transaction_ref="TXN-UPI-9012481",
            complaint_id=cmp1042.id,
            sender_account_id=acc_victim.id,
            receiver_account_id=acc_a.id,
            amount=125000.0,
            payment_channel="UPI (Immediate)",
            timestamp=now - datetime.timedelta(minutes=75),
            hop_number=1,
            status="COMPLETED",
            suspicious_flag=True
        ),
        Transaction(
            transaction_ref="TXN-IMPS-3487104",
            complaint_id=cmp1042.id,
            sender_account_id=acc_a.id,
            receiver_account_id=acc_b.id,
            amount=75000.0,
            payment_channel="IMPS Rapid",
            timestamp=now - datetime.timedelta(minutes=68),
            hop_number=2,
            status="COMPLETED",
            suspicious_flag=True
        ),
        Transaction(
            transaction_ref="TXN-IMPS-3485529",
            complaint_id=cmp1042.id,
            sender_account_id=acc_a.id,
            receiver_account_id=acc_c.id,
            amount=50000.0,
            payment_channel="IMPS Rapid",
            timestamp=now - datetime.timedelta(minutes=67),
            hop_number=2,
            status="COMPLETED",
            suspicious_flag=True
        ),
        Transaction(
            transaction_ref="TXN-NEFT-7108129",
            complaint_id=cmp1042.id,
            sender_account_id=acc_b.id,
            receiver_account_id=acc_mule_d.id,
            amount=75000.0,
            payment_channel="NEFT Rapid",
            timestamp=now - datetime.timedelta(minutes=55),
            hop_number=3,
            status="COMPLETED",
            suspicious_flag=True
        ),
        Transaction(
            transaction_ref="TXN-UPI-5526291",
            complaint_id=cmp1042.id,
            sender_account_id=acc_c.id,
            receiver_account_id=acc_mule_e.id,
            amount=50000.0,
            payment_channel="UPI P2P",
            timestamp=now - datetime.timedelta(minutes=52),
            hop_number=3,
            status="COMPLETED",
            suspicious_flag=True
        )
    ]
    db.add_all(txs)
    db.flush()

    # Seed Prediction for CMP-1042:
    # WHERE: Vijay Nagar, Indore (87% CRITICAL)
    # WHEN: Next 2–4 Hours
    # RISK: 87% CRITICAL
    # WHY: High Mule-Network Similarity
    # Top 3 Locations:
    # 1. Vijay Nagar, Indore - 87% (CRITICAL)
    # 2. Palasia, Indore - 61% (HIGH)
    # 3. Rau, Indore - 34% (MEDIUM)
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
        PredictionLocation(
            prediction_id=pred_1042.id,
            cluster_id=clusters[0].id,
            location_name="Vijay Nagar, Indore",
            rank=1,
            probability=0.87,
            risk_level="CRITICAL",
            distance_km=186.4,
            reasoning="High Mule-Network Similarity & Recent ATM Cashier Activity",
            latitude=22.7533,
            longitude=75.8937
        ),
        PredictionLocation(
            prediction_id=pred_1042.id,
            cluster_id=clusters[1].id,
            location_name="Palasia, Indore",
            rank=2,
            probability=0.61,
            risk_level="HIGH",
            distance_km=189.1,
            reasoning="Secondary ATM Cluster linked to Mule B layering account",
            latitude=22.7244,
            longitude=75.8839
        ),
        PredictionLocation(
            prediction_id=pred_1042.id,
            cluster_id=clusters[2].id,
            location_name="Rau, Indore",
            rank=3,
            probability=0.34,
            risk_level="MEDIUM",
            distance_km=198.7,
            reasoning="Outlying highway ATM node with low historical frequency",
            latitude=22.6288,
            longitude=75.8080
        )
    ]
    db.add_all(pred_locs)

    # Seed Alert for CMP-1042
    alert_1042 = Alert(
        complaint_id=cmp1042.id,
        prediction_id=pred_1042.id,
        title="CRITICAL CASH-OUT IMMINENT: Vijay Nagar, Indore (CMP-1042)",
        severity="CRITICAL",
        location_name="Vijay Nagar, Indore",
        risk_score=0.87,
        expected_window="Next 2–4 Hours",
        amount_at_risk=125000.0,
        status="NEW",
        created_at=now - datetime.timedelta(minutes=40)
    )
    db.add(alert_1042)

    # Seed Additional Seed Complaints to create rich ecosystem
    mock_fraud_types = ["Investment Scam", "UPI / QR Code Fraud", "Part-time Job Fraud", "Digital Arrest / Sextortion", "Loan App Extortion"]
    mock_districts = [
        ("Indore", "Palasia, Indore", "Madhya Pradesh"),
        ("Bhopal", "MP Nagar, Bhopal", "Madhya Pradesh"),
        ("Ujjain", "Freeganj, Ujjain", "Madhya Pradesh"),
        ("Indore", "Vijay Nagar, Indore", "Madhya Pradesh"),
        ("Bhopal", "Arera Hills, Bhopal", "Madhya Pradesh"),
        ("Jabalpur", "Civic Center, Jabalpur", "Madhya Pradesh"),
        ("Gwalior", "City Center, Gwalior", "Madhya Pradesh")
    ]
    channels = ["UPI", "IMPS", "NetBanking", "CreditCard"]

    for i in range(1, 45):
        num = f"CMP-{1000 + i}"
        if num == "CMP-1042":
            continue
        dist_info = random.choice(mock_districts)
        f_type = random.choice(mock_fraud_types)
        amt = float(random.choice([15000, 28000, 45000, 62000, 95000, 180000, 240000]))
        r_score = round(random.uniform(0.40, 0.89), 2)
        r_level = "CRITICAL" if r_score >= 0.80 else ("HIGH" if r_score >= 0.60 else "MEDIUM")

        c = Complaint(
            complaint_number=num,
            fraud_type=f_type,
            amount=amt,
            victim_name=f"Citizen {i}",
            victim_phone=f"+91 9{random.randint(100000000, 999999999)}",
            victim_location=f"{dist_info[1]}, {dist_info[2]}",
            state=dist_info[2],
            district=dist_info[0],
            payment_channel=random.choice(channels),
            reported_at=now - datetime.timedelta(hours=random.randint(2, 72)),
            incident_time=now - datetime.timedelta(hours=random.randint(3, 76)),
            risk_level=r_level,
            risk_score=r_score,
            prediction_status="COMPLETED" if r_score > 0.65 else "PENDING",
            case_status="ACTIVE"
        )
        db.add(c)

    # Seed Initial Audit Log
    db.add(AuditLog(
        officer_name="System Supervisor",
        role="I4C_ADMIN",
        action="SYSTEM_INITIALIZED",
        case_number="SYSTEM",
        details="CyberShield AI National Predictive Engine initialized with 6 location clusters and active LEA nodes."
    ))

    db.commit()
    print("[Seed] Successfully seeded all database entities, CMP-1042, accounts, and demo credentials!")

if __name__ == "__main__":
    Base.metadata.create_all(bind=engine)
    db = SessionLocal()
    seed_database(db)
    db.close()
