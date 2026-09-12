"""
CyberShield AI — Domain-Meaningful Synthetic Cybercrime Dataset Generator (v2)
Smart India Hackathon SIH26184

Remediations applied in v2:
1. Diversified cash-out target distribution:
   - 40% Primary beneficiary mule home/corridor
   - 30% Intermediary layering account corridor
   - 30% Dynamic commercial hotspot / high-ATM-density hub
2. Time-aware causal historical cluster statistics:
   - Cluster cash-out count, amount, and recent activity calculated using events BEFORE time T only.
3. Designated cold-start test cohort:
   - 400 mule accounts reserved exclusively for cold-start evaluation (0% training overlap).
"""

import os
import json
import math
import random
import numpy as np
import pandas as pd
from datetime import datetime, timedelta
from typing import Dict, Any, List, Tuple

RANDOM_SEED = 42
TOTAL_COMPLAINTS = 20000
TOTAL_ACCOUNTS = 12000
TOTAL_ATMS = 2200

CLUSTERS_DATA = [
    # Madhya Pradesh (Indore & Bhopal corridor)
    {"id": 1, "name": "Vijay Nagar, Indore", "city": "Indore", "state": "Madhya Pradesh", "lat": 22.7533, "lon": 75.8937, "atm_density": 28, "base_risk": 0.88},
    {"id": 2, "name": "Palasia, Indore", "city": "Indore", "state": "Madhya Pradesh", "lat": 22.7244, "lon": 75.8839, "atm_density": 22, "base_risk": 0.72},
    {"id": 3, "name": "Rau, Indore", "city": "Indore", "state": "Madhya Pradesh", "lat": 22.6288, "lon": 75.8080, "atm_density": 10, "base_risk": 0.42},
    {"id": 4, "name": "Bhanwarkuan, Indore", "city": "Indore", "state": "Madhya Pradesh", "lat": 22.6934, "lon": 75.8672, "atm_density": 19, "base_risk": 0.65},
    {"id": 5, "name": "Sarafa Bazaar, Indore", "city": "Indore", "state": "Madhya Pradesh", "lat": 22.7179, "lon": 75.8544, "atm_density": 15, "base_risk": 0.58},
    {"id": 6, "name": "Scheme 54, Indore", "city": "Indore", "state": "Madhya Pradesh", "lat": 22.7610, "lon": 75.8992, "atm_density": 24, "base_risk": 0.81},
    {"id": 7, "name": "MP Nagar, Bhopal", "city": "Bhopal", "state": "Madhya Pradesh", "lat": 23.2332, "lon": 77.4343, "atm_density": 26, "base_risk": 0.84},
    {"id": 8, "name": "New Market, Bhopal", "city": "Bhopal", "state": "Madhya Pradesh", "lat": 23.2363, "lon": 77.4013, "atm_density": 18, "base_risk": 0.60},
    {"id": 9, "name": "Kolar Road, Bhopal", "city": "Bhopal", "state": "Madhya Pradesh", "lat": 23.1856, "lon": 77.4222, "atm_density": 12, "base_risk": 0.48},
    {"id": 10, "name": "Arera Colony, Bhopal", "city": "Bhopal", "state": "Madhya Pradesh", "lat": 23.2132, "lon": 77.4412, "atm_density": 16, "base_risk": 0.52},
    {"id": 11, "name": "Freeganj, Ujjain", "city": "Ujjain", "state": "Madhya Pradesh", "lat": 23.1824, "lon": 75.7892, "atm_density": 14, "base_risk": 0.55},
    {"id": 12, "name": "Civic Center, Jabalpur", "city": "Jabalpur", "state": "Madhya Pradesh", "lat": 23.1686, "lon": 79.9339, "atm_density": 15, "base_risk": 0.53},

    # Delhi NCR
    {"id": 13, "name": "Connaught Place, Delhi", "city": "Delhi", "state": "Delhi", "lat": 28.6315, "lon": 77.2167, "atm_density": 35, "base_risk": 0.85},
    {"id": 14, "name": "Karol Bagh, Delhi", "city": "Delhi", "state": "Delhi", "lat": 28.6514, "lon": 77.1907, "atm_density": 30, "base_risk": 0.78},
    {"id": 15, "name": "Laxmi Nagar, Delhi", "city": "Delhi", "state": "Delhi", "lat": 28.6308, "lon": 77.2773, "atm_density": 25, "base_risk": 0.74},
    {"id": 16, "name": "Rohini Sector 10, Delhi", "city": "Delhi", "state": "Delhi", "lat": 28.7159, "lon": 77.1172, "atm_density": 20, "base_risk": 0.62},
    {"id": 17, "name": "Saket District Centre, Delhi", "city": "Delhi", "state": "Delhi", "lat": 28.5245, "lon": 77.2066, "atm_density": 28, "base_risk": 0.79},
    {"id": 18, "name": "Sector 18, Noida", "city": "Noida", "state": "Uttar Pradesh", "lat": 28.5708, "lon": 77.3271, "atm_density": 32, "base_risk": 0.83},
    {"id": 19, "name": "Cyber City, Gurugram", "city": "Gurugram", "state": "Haryana", "lat": 28.4950, "lon": 77.0895, "atm_density": 34, "base_risk": 0.86},

    # Maharashtra (Mumbai & Pune)
    {"id": 20, "name": "Bandra Kurla Complex, Mumbai", "city": "Mumbai", "state": "Maharashtra", "lat": 19.0657, "lon": 72.8687, "atm_density": 40, "base_risk": 0.89},
    {"id": 21, "name": "Andheri East, Mumbai", "city": "Mumbai", "state": "Maharashtra", "lat": 19.1136, "lon": 72.8697, "atm_density": 38, "base_risk": 0.84},
    {"id": 22, "name": "Borivali West, Mumbai", "city": "Mumbai", "state": "Maharashtra", "lat": 19.2307, "lon": 72.8567, "atm_density": 26, "base_risk": 0.68},
    {"id": 23, "name": "Dadar Commercial, Mumbai", "city": "Mumbai", "state": "Maharashtra", "lat": 19.0178, "lon": 72.8478, "atm_density": 32, "base_risk": 0.77},
    {"id": 24, "name": "Thane West Station Strip, Thane", "city": "Thane", "state": "Maharashtra", "lat": 19.1860, "lon": 72.9759, "atm_density": 28, "base_risk": 0.73},
    {"id": 25, "name": "Vashi Sector 17, Navi Mumbai", "city": "Navi Mumbai", "state": "Maharashtra", "lat": 19.0760, "lon": 72.9986, "atm_density": 25, "base_risk": 0.71},
    {"id": 26, "name": "Hinjewadi Phase 1, Pune", "city": "Pune", "state": "Maharashtra", "lat": 18.5913, "lon": 73.7389, "atm_density": 24, "base_risk": 0.75},
    {"id": 27, "name": "Kothrud, Pune", "city": "Pune", "state": "Maharashtra", "lat": 18.5074, "lon": 73.8077, "atm_density": 20, "base_risk": 0.63},
    {"id": 28, "name": "Viman Nagar, Pune", "city": "Pune", "state": "Maharashtra", "lat": 18.5679, "lon": 73.9143, "atm_density": 22, "base_risk": 0.70},
    {"id": 29, "name": "Shivaji Nagar, Pune", "city": "Pune", "state": "Maharashtra", "lat": 18.5308, "lon": 73.8475, "atm_density": 25, "base_risk": 0.74},

    # Karnataka (Bengaluru)
    {"id": 30, "name": "Koramangala 5th Block, Bengaluru", "city": "Bengaluru", "state": "Karnataka", "lat": 12.9352, "lon": 77.6245, "atm_density": 36, "base_risk": 0.86},
    {"id": 31, "name": "Indiranagar 100ft Road, Bengaluru", "city": "Bengaluru", "state": "Karnataka", "lat": 12.9719, "lon": 77.6412, "atm_density": 32, "base_risk": 0.82},
    {"id": 32, "name": "Whitefield IT Hub, Bengaluru", "city": "Bengaluru", "state": "Karnataka", "lat": 12.9698, "lon": 77.7500, "atm_density": 26, "base_risk": 0.76},
    {"id": 33, "name": "HSR Layout Sector 1, Bengaluru", "city": "Bengaluru", "state": "Karnataka", "lat": 12.9121, "lon": 77.6446, "atm_density": 25, "base_risk": 0.73},
    {"id": 34, "name": "Jayanagar 4th Block, Bengaluru", "city": "Bengaluru", "state": "Karnataka", "lat": 12.9299, "lon": 77.5824, "atm_density": 22, "base_risk": 0.67},
    {"id": 35, "name": "Electronic City Phase 1, Bengaluru", "city": "Bengaluru", "state": "Karnataka", "lat": 12.8399, "lon": 77.6770, "atm_density": 20, "base_risk": 0.65},

    # Telangana (Hyderabad)
    {"id": 36, "name": "Hitec City, Hyderabad", "city": "Hyderabad", "state": "Telangana", "lat": 17.4435, "lon": 78.3772, "atm_density": 34, "base_risk": 0.85},
    {"id": 37, "name": "Madhapur Main Road, Hyderabad", "city": "Hyderabad", "state": "Telangana", "lat": 17.4483, "lon": 78.3915, "atm_density": 28, "base_risk": 0.80},
    {"id": 38, "name": "Banjara Hills Road 12, Hyderabad", "city": "Hyderabad", "state": "Telangana", "lat": 17.4156, "lon": 78.4350, "atm_density": 26, "base_risk": 0.76},
    {"id": 39, "name": "Ameerpet Metro Hub, Hyderabad", "city": "Hyderabad", "state": "Telangana", "lat": 17.4375, "lon": 78.4483, "atm_density": 30, "base_risk": 0.79},
    {"id": 40, "name": "Kukatpally Housing Board, Hyderabad", "city": "Hyderabad", "state": "Telangana", "lat": 17.4938, "lon": 78.3995, "atm_density": 24, "base_risk": 0.72},
    {"id": 41, "name": "Secunderabad Station Hub, Hyderabad", "city": "Hyderabad", "state": "Telangana", "lat": 17.4399, "lon": 78.4983, "atm_density": 27, "base_risk": 0.74},

    # West Bengal (Kolkata)
    {"id": 42, "name": "Salt Lake Sector V, Kolkata", "city": "Kolkata", "state": "West Bengal", "lat": 22.5804, "lon": 88.4378, "atm_density": 32, "base_risk": 0.84},
    {"id": 43, "name": "Park Street Commercial, Kolkata", "city": "Kolkata", "state": "West Bengal", "lat": 22.5535, "lon": 88.3524, "atm_density": 28, "base_risk": 0.78},
    {"id": 44, "name": "New Town Action Area 1, Kolkata", "city": "Kolkata", "state": "West Bengal", "lat": 22.5930, "lon": 88.4639, "atm_density": 24, "base_risk": 0.72},
    {"id": 45, "name": "Gariahat Crossing, Kolkata", "city": "Kolkata", "state": "West Bengal", "lat": 22.5186, "lon": 88.3653, "atm_density": 22, "base_risk": 0.66},
    {"id": 46, "name": "Howrah Station Strip, Howrah", "city": "Howrah", "state": "West Bengal", "lat": 22.5892, "lon": 88.3415, "atm_density": 26, "base_risk": 0.75},
    {"id": 47, "name": "Dum Dum Metro Zone, Kolkata", "city": "Kolkata", "state": "West Bengal", "lat": 22.6433, "lon": 88.3967, "atm_density": 18, "base_risk": 0.60},

    # Rajasthan (Jaipur)
    {"id": 48, "name": "Malviya Nagar, Jaipur", "city": "Jaipur", "state": "Rajasthan", "lat": 26.8530, "lon": 75.8050, "atm_density": 22, "base_risk": 0.74},
    {"id": 49, "name": "Vaishali Nagar, Jaipur", "city": "Jaipur", "state": "Rajasthan", "lat": 26.9075, "lon": 75.7397, "atm_density": 20, "base_risk": 0.69},
    {"id": 50, "name": "Mansarovar Sector 3, Jaipur", "city": "Jaipur", "state": "Rajasthan", "lat": 26.8524, "lon": 75.7684, "atm_density": 18, "base_risk": 0.61},
    {"id": 51, "name": "C-Scheme Commercial, Jaipur", "city": "Jaipur", "state": "Rajasthan", "lat": 26.9124, "lon": 75.8033, "atm_density": 24, "base_risk": 0.76},
    {"id": 52, "name": "Raja Park, Jaipur", "city": "Jaipur", "state": "Rajasthan", "lat": 26.8966, "lon": 75.8276, "atm_density": 19, "base_risk": 0.64},
    {"id": 53, "name": "Tonk Road Flyover Zone, Jaipur", "city": "Jaipur", "state": "Rajasthan", "lat": 26.8654, "lon": 75.8001, "atm_density": 16, "base_risk": 0.58},

    # Uttar Pradesh (Lucknow)
    {"id": 54, "name": "Hazratganj Main, Lucknow", "city": "Lucknow", "state": "Uttar Pradesh", "lat": 26.8500, "lon": 80.9499, "atm_density": 26, "base_risk": 0.79},
    {"id": 55, "name": "Gomti Nagar Vibhuti Khand, Lucknow", "city": "Lucknow", "state": "Uttar Pradesh", "lat": 26.8667, "lon": 81.0000, "atm_density": 28, "base_risk": 0.82},
    {"id": 56, "name": "Alambagh Bus Terminal, Lucknow", "city": "Lucknow", "state": "Uttar Pradesh", "lat": 26.8145, "lon": 80.9023, "atm_density": 22, "base_risk": 0.70},
    {"id": 57, "name": "Indira Nagar Sector 14, Lucknow", "city": "Lucknow", "state": "Uttar Pradesh", "lat": 26.8833, "lon": 80.9833, "atm_density": 18, "base_risk": 0.63},
    {"id": 58, "name": "Aliganj Sector H, Lucknow", "city": "Lucknow", "state": "Uttar Pradesh", "lat": 26.8942, "lon": 80.9421, "atm_density": 16, "base_risk": 0.59},
    {"id": 59, "name": "Chowk Bazaar, Lucknow", "city": "Lucknow", "state": "Uttar Pradesh", "lat": 26.8672, "lon": 80.9034, "atm_density": 19, "base_risk": 0.65},
    {"id": 60, "name": "Charbagh Railway Hub, Lucknow", "city": "Lucknow", "state": "Uttar Pradesh", "lat": 26.8315, "lon": 80.9234, "atm_density": 24, "base_risk": 0.75},
]

BANKS = [
    "State Bank of India", "HDFC Bank", "ICICI Bank", "Axis Bank",
    "Punjab National Bank", "Bank of Baroda", "Canara Bank", "Union Bank of India"
]

FRAUD_TYPES = [
    {"type": "Investment Scam", "weight": 0.28, "base_amount": 120000, "delay_mean": 240, "hop_weights": [0.1, 0.3, 0.4, 0.2]},
    {"type": "UPI / QR Code Fraud", "weight": 0.32, "base_amount": 35000, "delay_mean": 90, "hop_weights": [0.3, 0.4, 0.2, 0.1]},
    {"type": "Digital Arrest / Extortion", "weight": 0.18, "base_amount": 250000, "delay_mean": 180, "hop_weights": [0.05, 0.25, 0.45, 0.25]},
    {"type": "Part-Time Job Fraud", "weight": 0.14, "base_amount": 65000, "delay_mean": 150, "hop_weights": [0.2, 0.4, 0.3, 0.1]},
    {"type": "Loan App Extortion", "weight": 0.08, "base_amount": 40000, "delay_mean": 120, "hop_weights": [0.25, 0.45, 0.2, 0.1]}
]

PAYMENT_CHANNELS = ["UPI", "IMPS", "NEFT", "RTGS"]

def haversine_km(lat1: float, lon1: float, lat2: float, lon2: float) -> float:
    R = 6371.0
    dlat = math.radians(lat2 - lat1)
    dlon = math.radians(lon2 - lon1)
    a = math.sin(dlat / 2.0)**2 + math.cos(math.radians(lat1)) * math.cos(math.radians(lat2)) * math.sin(dlon / 2.0)**2
    c = 2.0 * math.atan2(math.sqrt(a), math.sqrt(1.0 - a))
    return R * c

def generate_full_synthetic_dataset(output_dir: str = "ml/data") -> Dict[str, Any]:
    print("=" * 70)
    print(f"[Generator v2] Generating Diversified Synthetic Cybercrime Dataset (Seed={RANDOM_SEED})")
    print("=" * 70)

    os.makedirs(output_dir, exist_ok=True)
    random.seed(RANDOM_SEED)
    np.random.seed(RANDOM_SEED)

    start_time = datetime(2026, 1, 1, 0, 0, 0)

    # 1. Location Clusters
    clusters_df = pd.DataFrame(CLUSTERS_DATA)
    cluster_id_to_obj = {c["id"]: c for c in CLUSTERS_DATA}

    # 2. ATMs
    atms_records = []
    atm_id_seq = 1
    for c in CLUSTERS_DATA:
        n_atms = random.randint(25, 45)
        for _ in range(n_atms):
            lat_offset = random.gauss(0, 0.012)
            lon_offset = random.gauss(0, 0.012)
            atms_records.append({
                "atm_id": atm_id_seq,
                "atm_code": f"ATM-{c['city'][:3].upper()}-{atm_id_seq:04d}",
                "bank": random.choice(BANKS),
                "cluster_id": c["id"],
                "city": c["city"],
                "state": c["state"],
                "latitude": round(c["lat"] + lat_offset, 6),
                "longitude": round(c["lon"] + lon_offset, 6),
                "cash_limit": random.choice([20000, 40000, 50000, 100000]),
                "status": "OPERATIONAL"
            })
            atm_id_seq += 1

    atms_df = pd.DataFrame(atms_records)
    print(f"[Generator v2] Generated {len(atms_df)} ATMs across {len(clusters_df)} clusters.")

    # 3. Accounts (12,000 total accounts, 2,400 mules)
    # Split mules: 2,000 standard temporal mules, 400 dedicated cold-start mules
    accounts_records = []
    n_mules = 2400
    cold_start_mule_threshold = 2000

    for a_id in range(1, TOTAL_ACCOUNTS + 1):
        is_mule = (a_id <= n_mules)
        is_cold_start = (a_id > cold_start_mule_threshold and a_id <= n_mules)

        if is_mule:
            acc_type = "MULE"
            risk = round(random.uniform(0.72, 0.98), 2)
            deg = random.randint(4, 18)
        elif a_id <= n_mules + 3000:
            acc_type = "INTERMEDIARY"
            risk = round(random.uniform(0.35, 0.68), 2)
            deg = random.randint(2, 6)
        else:
            acc_type = "REGULAR"
            risk = round(random.uniform(0.02, 0.25), 2)
            deg = random.randint(1, 3)

        home_cluster = random.choice(CLUSTERS_DATA)
        accounts_records.append({
            "account_id": a_id,
            "account_number": f"ACC-{1000000 + a_id}",
            "bank": random.choice(BANKS),
            "account_type": acc_type,
            "is_mule": is_mule,
            "is_cold_start_mule": is_cold_start,
            "home_cluster_id": home_cluster["id"],
            "home_city": home_cluster["city"],
            "home_state": home_cluster["state"],
            "risk_score": risk,
            "degree": deg,
            "created_at": (start_time - timedelta(days=random.randint(60, 700))).isoformat()
        })

    accounts_df = pd.DataFrame(accounts_records)
    temporal_mule_ids = accounts_df[accounts_df["is_mule"] & (~accounts_df["is_cold_start_mule"])]["account_id"].values
    cold_mule_ids = accounts_df[accounts_df["is_cold_start_mule"]]["account_id"].values
    inter_acc_ids = accounts_df[accounts_df["account_type"] == "INTERMEDIARY"]["account_id"].values
    victim_acc_ids = accounts_df[accounts_df["account_type"] == "REGULAR"]["account_id"].values

    account_to_cluster_map = dict(zip(accounts_df["account_id"], accounts_df["home_cluster_id"]))

    print(f"[Generator v2] Generated {len(accounts_df)} accounts ({len(temporal_mule_ids)} temporal mules, {len(cold_mule_ids)} cold-start mules).")

    # 4. Complaints, Transactions & Withdrawals with Chronological Running History
    complaints_records = []
    transactions_records = []
    withdrawals_records = []
    tx_id_seq = 1

    days_span = 180
    f_types = [ft["type"] for ft in FRAUD_TYPES]
    f_probs = [ft["weight"] for ft in FRAUD_TYPES]

    # Initialize running historical cluster stats (with slight empirical warm-up baseline)
    cluster_history = {
        c["id"]: {
            "cashout_count": int(c.get("atm_density", 15) * 8), # Prior baseline
            "cashout_amount": float(c.get("atm_density", 15) * 8 * 45000.0),
            "timestamps": [],
            "fraud_type_counts": {ft: 15 for ft in f_types}
        }
        for c in CLUSTERS_DATA
    }

    # Pending withdrawals buffer: list of (withdrawal_time, cluster_id, amount, fraud_type)
    pending_withdrawals = []

    for c_idx in range(1, TOTAL_COMPLAINTS + 1):
        # Progress chronologically
        progress_ratio = c_idx / TOTAL_COMPLAINTS
        incident_day = int(progress_ratio * days_span)
        incident_minute = random.randint(0, 1439)
        incident_time = start_time + timedelta(days=incident_day, minutes=incident_minute)

        # Update historical statistics with any withdrawals that have ALREADY occurred prior to incident_time
        still_pending = []
        for w_time, w_cid, w_amt, w_ft in pending_withdrawals:
            if w_time <= incident_time:
                ch = cluster_history[w_cid]
                ch["cashout_count"] += 1
                ch["cashout_amount"] += w_amt
                ch["timestamps"].append(w_time)
                ch["fraud_type_counts"][w_ft] = ch["fraud_type_counts"].get(w_ft, 0) + 1
            else:
                still_pending.append((w_time, w_cid, w_amt, w_ft))
        pending_withdrawals = still_pending

        ft_choice = np.random.choice(FRAUD_TYPES, p=f_probs)
        fraud_type = ft_choice["type"]

        base_amt = ft_choice["base_amount"]
        amount = round(float(np.random.lognormal(mean=np.log(base_amt), sigma=0.45)), -2)
        amount = max(10000.0, min(1500000.0, amount))

        channel = random.choices(PAYMENT_CHANNELS, weights=[0.65, 0.22, 0.08, 0.05])[0]

        delay_mean = ft_choice["delay_mean"]
        complaint_delay = int(np.random.gamma(shape=2.5, scale=delay_mean / 2.5))
        complaint_delay = max(15, min(2880, complaint_delay))
        complaint_timestamp = incident_time + timedelta(minutes=complaint_delay)

        # Victim origin
        victim_origin_cluster = random.choice(CLUSTERS_DATA)
        v_lat = victim_origin_cluster["lat"] + random.uniform(-0.1, 0.1)
        v_lon = victim_origin_cluster["lon"] + random.uniform(-0.1, 0.1)

        # Select beneficiary mule
        # Reserve last 1,500 complaints for cold-start test split with cold-start mules
        is_cold_start_case = (c_idx > (TOTAL_COMPLAINTS - 1500))
        if is_cold_start_case and len(cold_mule_ids) > 0:
            beneficiary_mule_id = int(np.random.choice(cold_mule_ids))
        else:
            beneficiary_mule_id = int(np.random.choice(temporal_mule_ids))

        beneficiary_home_cluster_id = account_to_cluster_map[beneficiary_mule_id]

        # Multi-hop layering construction
        hop_weights = ft_choice["hop_weights"]
        n_hops = int(np.random.choice([1, 2, 3, 4], p=hop_weights))

        v_acc_id = int(np.random.choice(victim_acc_ids))
        current_sender = v_acc_id
        current_tx_time = incident_time
        chain_tx_ids = []
        hop_accounts = [current_sender]
        intermediary_cluster_ids = []

        for hop in range(1, n_hops + 1):
            hop_interval = random.randint(4, 25)
            current_tx_time = current_tx_time + timedelta(minutes=hop_interval)

            if hop == n_hops:
                receiver = beneficiary_mule_id
            else:
                receiver = int(np.random.choice(inter_acc_ids))
                intermediary_cluster_ids.append(account_to_cluster_map[receiver])

            hop_accounts.append(receiver)
            tx_record = {
                "transaction_id": tx_id_seq,
                "complaint_id": c_idx,
                "from_account": current_sender,
                "to_account": receiver,
                "amount": round(amount * (0.98 ** (hop - 1)), 2),
                "bank": random.choice(BANKS),
                "channel": channel,
                "timestamp": current_tx_time.isoformat(),
                "hop_number": hop
            }
            transactions_records.append(tx_record)
            chain_tx_ids.append(tx_id_seq)
            tx_id_seq += 1

            # Layering branches
            n_branches = random.choice([2, 3, 3, 4])
            split_amount = round((amount * 0.4) / n_branches, 2)
            for b_idx in range(n_branches):
                branch_receiver = int(np.random.choice(temporal_mule_ids if hop == n_hops else inter_acc_ids))
                transactions_records.append({
                    "transaction_id": tx_id_seq,
                    "complaint_id": c_idx,
                    "from_account": current_sender,
                    "to_account": branch_receiver,
                    "amount": split_amount,
                    "bank": random.choice(BANKS),
                    "channel": channel,
                    "timestamp": (current_tx_time + timedelta(minutes=random.randint(1, 10))).isoformat(),
                    "hop_number": hop
                })
                tx_id_seq += 1

            current_sender = receiver

        last_tx_time = current_tx_time

        # DIVERSIFIED CASH-OUT TARGET GENERATION (40% / 30% / 30%)
        corridor_rand = random.random()
        if corridor_rand < 0.40:
            # 40%: Primary beneficiary mule home cluster
            target_cluster_id = beneficiary_home_cluster_id
            target_mechanism = "beneficiary_mule_corridor"
        elif corridor_rand < 0.70 and len(intermediary_cluster_ids) > 0:
            # 30%: Intermediary network corridor
            target_cluster_id = random.choice(intermediary_cluster_ids)
            target_mechanism = "intermediary_network_corridor"
        else:
            # 30%: Dynamic commercial hotspot or nearby cluster weighted by ATM density & state proximity
            mule_state = cluster_id_to_obj[beneficiary_home_cluster_id]["state"]
            vic_state = victim_origin_cluster["state"]
            nearby_clusters = [c for c in CLUSTERS_DATA if c["state"] in [mule_state, vic_state]]
            if not nearby_clusters:
                nearby_clusters = CLUSTERS_DATA
            # Weight by ATM density * base risk
            weights = [c["atm_density"] * c["base_risk"] for c in nearby_clusters]
            w_sum = sum(weights)
            p_weights = [w / w_sum for w in weights]
            target_cluster_id = int(np.random.choice([c["id"] for c in nearby_clusters], p=p_weights))
            target_mechanism = "dynamic_hotspot_hub"

        target_cluster = cluster_id_to_obj[target_cluster_id]

        # Time-to-cashout with realistic dispersion
        if channel == "UPI":
            cashout_delay_minutes = int(np.random.normal(loc=110, scale=35))
        else:
            cashout_delay_minutes = int(np.random.normal(loc=210, scale=55))
        cashout_delay_minutes = max(30, min(480, cashout_delay_minutes))

        withdrawal_time = last_tx_time + timedelta(minutes=cashout_delay_minutes)

        # Ground truth ATM in target cluster
        cl_atms = atms_df[atms_df["cluster_id"] == target_cluster_id]
        if not cl_atms.empty:
            chosen_atm = cl_atms.sample(1).iloc[0]
            chosen_atm_id = int(chosen_atm["atm_id"])
            w_lat = chosen_atm["latitude"]
            w_lon = chosen_atm["longitude"]
        else:
            chosen_atm_id = 1
            w_lat = target_cluster["lat"]
            w_lon = target_cluster["lon"]

        # Record withdrawal target
        withdrawals_records.append({
            "withdrawal_id": c_idx,
            "complaint_id": c_idx,
            "account_id": beneficiary_mule_id,
            "atm_id": chosen_atm_id,
            "cluster_id": target_cluster_id,
            "timestamp": withdrawal_time.isoformat(),
            "amount": amount,
            "latitude": w_lat,
            "longitude": w_lon
        })

        # Append to pending buffer so future complaints see this event only AFTER withdrawal_time
        pending_withdrawals.append((withdrawal_time, target_cluster_id, amount, fraud_type))

        # Extract causal historical statistics for target cluster at time T (incident_time)
        ch_target = cluster_history[target_cluster_id]
        recent_14d_acts = sum(1 for t in ch_target["timestamps"] if (incident_time - t).total_seconds() <= 14 * 86400)

        complaints_records.append({
            "complaint_id": c_idx,
            "complaint_number": f"CMP-{1000 + c_idx}",
            "fraud_type": fraud_type,
            "amount": amount,
            "payment_channel": channel,
            "incident_timestamp": incident_time.isoformat(),
            "complaint_delay_minutes": complaint_delay,
            "complaint_timestamp": complaint_timestamp.isoformat(),
            "victim_state": victim_origin_cluster["state"],
            "victim_district": victim_origin_cluster["city"],
            "victim_city": victim_origin_cluster["city"],
            "victim_lat": round(v_lat, 6),
            "victim_lon": round(v_lon, 6),
            "beneficiary_mule_id": beneficiary_mule_id,
            "target_cluster_id": target_cluster_id,
            "target_atm_id": chosen_atm_id,
            "target_mechanism": target_mechanism,
            "last_tx_timestamp": last_tx_time.isoformat(),
            "minutes_until_cashout": cashout_delay_minutes,
            "withdrawal_timestamp": withdrawal_time.isoformat(),
            "hop_count": n_hops,
            "is_cold_start": is_cold_start_case,
            # Causal historical aggregates for complaint at time T
            "hist_cluster_cashout_count": ch_target["cashout_count"],
            "hist_cluster_cashout_amount": ch_target["cashout_amount"],
            "hist_recent_activity": recent_14d_acts,
            "hist_fraud_type_freq": ch_target["fraud_type_counts"].get(fraud_type, 0)
        })

        if c_idx % 5000 == 0:
            print(f"[Generator v2] Processed {c_idx} / {TOTAL_COMPLAINTS} complaints...")

    complaints_df = pd.DataFrame(complaints_records)
    transactions_df = pd.DataFrame(transactions_records)
    withdrawals_df = pd.DataFrame(withdrawals_records)

    # Save to compressed CSV and standard CSV
    clusters_path = os.path.join(output_dir, "clusters.csv.gz")
    atms_path = os.path.join(output_dir, "atms.csv.gz")
    accounts_path = os.path.join(output_dir, "accounts.csv.gz")
    complaints_path = os.path.join(output_dir, "complaints.csv.gz")
    transactions_path = os.path.join(output_dir, "transactions.csv.gz")
    withdrawals_path = os.path.join(output_dir, "withdrawals.csv.gz")

    clusters_df.to_csv(clusters_path, index=False, compression="gzip")
    atms_df.to_csv(atms_path, index=False, compression="gzip")
    accounts_df.to_csv(accounts_path, index=False, compression="gzip")
    complaints_df.to_csv(complaints_path, index=False, compression="gzip")
    transactions_df.to_csv(transactions_path, index=False, compression="gzip")
    withdrawals_df.to_csv(withdrawals_path, index=False, compression="gzip")

    clusters_df.to_csv(os.path.join(output_dir, "clusters.csv"), index=False)
    complaints_df.head(100).to_csv(os.path.join(output_dir, "complaints_sample.csv"), index=False)

    summary = {
        "generated_at": datetime.utcnow().isoformat(),
        "random_seed": RANDOM_SEED,
        "dataset_type": "domain_meaningful_synthetic_v2",
        "version": "v2",
        "complaints_count": len(complaints_df),
        "transactions_count": len(transactions_df),
        "accounts_count": len(accounts_df),
        "atms_count": len(atms_df),
        "clusters_count": len(clusters_df),
        "withdrawals_count": len(withdrawals_df),
        "cold_start_complaints": int(complaints_df["is_cold_start"].sum()),
        "target_mechanisms": {
            k: int(v) for k, v in complaints_df["target_mechanism"].value_counts().items()
        },
        "cities": sorted(list(clusters_df["city"].unique())),
        "fraud_types": f_types,
        "files": {
            "clusters": clusters_path,
            "atms": atms_path,
            "accounts": accounts_path,
            "complaints": complaints_path,
            "transactions": transactions_path,
            "withdrawals": withdrawals_path
        }
    }

    meta_path = os.path.join(output_dir, "synthetic_dataset_manifest.json")
    with open(meta_path, "w") as f:
        json.dump(summary, f, indent=2)

    print(f"[Generator v2] Successfully generated and persisted dataset to {output_dir}")
    print(f" - Complaints: {len(complaints_df)}")
    print(f" - Target Mechanisms: {summary['target_mechanisms']}")
    print(f" - Cold-start Complaints: {summary['cold_start_complaints']}")
    return summary

if __name__ == "__main__":
    generate_full_synthetic_dataset()
