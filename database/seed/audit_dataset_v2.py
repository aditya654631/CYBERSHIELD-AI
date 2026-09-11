"""
Comprehensive Step 8B Metrics and Validation Script
Analyzes the freshly seeded Synthetic Dataset V2 in PostgreSQL.
"""

import math
import collections
from collections import Counter
from decimal import Decimal
import numpy as np

from backend.app.models.db import SessionLocal
from backend.app.models.models import (
    Complaint, Account, Transaction, ComplaintAccount, Withdrawal,
    LocationCluster, ATMLocation
)
from database.seed.synthetic_generator import DelhiSyntheticDataGenerator, ZONE_ADJACENCY
from database.seed.seed_config import SYNTHETIC_RANDOM_SEED, NUM_COMPLAINTS, NUM_ACCOUNTS

def haversine_km(lat1, lon1, lat2, lon2):
    R = 6371.0
    dlat = math.radians(lat2 - lat1)
    dlon = math.radians(lon2 - lon1)
    a = math.sin(dlat / 2.0)**2 + math.cos(math.radians(lat1)) * math.cos(math.radians(lat2)) * math.sin(dlon / 2.0)**2
    c = 2 * math.atan2(math.sqrt(a), math.sqrt(1.0 - a))
    return R * c

def run_analysis():
    db = SessionLocal()
    print("Running Step 8B Dataset Analysis on PostgreSQL...")

    # Fetch clusters & ATMs
    delhi_clusters = db.query(LocationCluster).filter(LocationCluster.state == "Delhi").all()
    cluster_by_id = {c.id: c for c in delhi_clusters}
    cluster_by_name = {c.cluster_name: c for c in delhi_clusters}
    all_delhi_cluster_names = [c.cluster_name for c in delhi_clusters]

    delhi_atms = db.query(ATMLocation).filter(ATMLocation.atm_code.like("ATM-DL-%")).all()
    atm_to_cluster = {a.id: a.cluster_id for a in delhi_atms}

    complaints = db.query(Complaint).filter(Complaint.complaint_number.like("CMP-DL-%")).order_by(Complaint.id).all()
    accounts = db.query(Account).filter(Account.account_number.like("SYN-DL-%")).all()
    acc_map = {a.id: a for a in accounts}

    # Debug scenarios from generator
    cluster_dicts = [
        {"name": c.cluster_name, "zone": c.district, "lat": c.center_lat, "lon": c.center_lon, "id": c.id, "risk": c.risk_score or 0.5, "atm_density": c.atm_count or 4}
        for c in delhi_clusters
    ]
    atm_dicts = [
        {"atm_code": a.atm_code, "bank_name": a.bank_name, "cluster_name": cluster_by_id[a.cluster_id].cluster_name, "id": a.id}
        for a in delhi_atms
    ]
    gen = DelhiSyntheticDataGenerator(SYNTHETIC_RANDOM_SEED)
    ds = gen.generate_dataset(cluster_dicts, atm_dicts, NUM_COMPLAINTS, NUM_ACCOUNTS)
    debug_scenarios = {d["complaint_number"]: d["scenario_pattern"] for d in ds["debug_metadata"]}

    # Map withdrawals by complaint_number directly from ds["withdrawals"]
    wdl_by_comp = {w["complaint_number"]: w for w in ds["withdrawals"]}

    pattern_counts = Counter()
    origin_target_count = 0
    same_origin_zone_count = 0
    same_terminal_zone_count = 0
    cross_zone_count = 0

    pattern_metrics = {
        "LOCAL": {"count": 0, "origin_target": 0, "same_terminal_zone": 0, "same_any_account_zone": 0, "dists": []},
        "MULE_CORRIDOR": {"count": 0, "origin_target": 0, "same_terminal_zone": 0, "same_any_account_zone": 0, "dists": []},
        "HISTORICAL_HOTSPOT": {"count": 0, "origin_target": 0, "same_terminal_zone": 0, "same_any_account_zone": 0, "dists": []},
        "CROSS_ZONE": {"count": 0, "origin_target": 0, "same_terminal_zone": 0, "same_any_account_zone": 0, "dists": []},
    }

    eval_samples = []

    for comp in complaints:
        pat = debug_scenarios.get(comp.complaint_number, "LOCAL")
        pattern_counts[pat] += 1

        raw_orig = comp.victim_location or ""
        origin_cluster_name = raw_orig.rsplit(", ", 1)[0] if ", " in raw_orig else raw_orig
        origin_cl = cluster_by_name.get(origin_cluster_name)
        origin_zone = comp.district

        comp_txns = db.query(Transaction).filter(Transaction.complaint_id == comp.id).order_by(Transaction.hop_number.desc(), Transaction.timestamp.desc()).all()
        if not comp_txns:
            continue
        terminal_tx = comp_txns[0]
        term_acc = acc_map.get(terminal_tx.receiver_account_id)
        term_zone = term_acc.district if term_acc else origin_zone

        involved_acc_ids = set()
        for t in comp_txns:
            involved_acc_ids.add(t.sender_account_id)
            involved_acc_ids.add(t.receiver_account_id)
        involved_zones = {acc_map[aid].district for aid in involved_acc_ids if aid in acc_map}

        # Check if withdrawal exists for this complaint
        w = wdl_by_comp.get(comp.complaint_number)
        if not w:
            continue

        target_cl_name = w["target_cluster_name"]
        target_cl = cluster_by_name.get(target_cl_name)
        if not target_cl:
            continue

        target_zone = target_cl.district

        is_origin = (origin_cl and target_cl.id == origin_cl.id)
        is_same_orig_zone = (target_zone == origin_zone)
        is_same_term_zone = (target_zone == term_zone)
        is_same_any_zone = (target_zone in involved_zones)
        is_cross = not is_same_orig_zone and not is_same_term_zone

        dist = haversine_km(origin_cl.center_lat, origin_cl.center_lon, target_cl.center_lat, target_cl.center_lon) if origin_cl else 0.0

        if is_origin:
            origin_target_count += 1
        if is_same_orig_zone:
            same_origin_zone_count += 1
        if is_same_term_zone:
            same_terminal_zone_count += 1
        if is_cross:
            cross_zone_count += 1

        pm = pattern_metrics[pat]
        pm["count"] += 1
        if is_origin:
            pm["origin_target"] += 1
        if is_same_term_zone:
            pm["same_terminal_zone"] += 1
        if is_same_any_zone:
            pm["same_any_account_zone"] += 1
        pm["dists"].append(dist)

        eval_samples.append({
            "complaint_number": comp.complaint_number,
            "origin_cluster_name": origin_cl.cluster_name if origin_cl else "",
            "origin_zone": origin_zone,
            "term_zone": term_zone,
            "target_cluster_name": target_cl.cluster_name,
            "target_cluster_id": target_cl.id,
            "pattern": pat,
            "fraud_type": comp.fraud_type,
            "payment_channel": comp.payment_channel,
        })

    N = len(eval_samples)
    print(f"\nTotal Analyzed Complaints with Cash-out: {N}")
    print("Scenario Pattern Distribution:")
    for pat, cnt in pattern_counts.items():
        print(f"  {pat}: {cnt} ({cnt / len(complaints) * 100:.2f}%)")

    print(f"\nTarget Geographic Rates (among {N} cash-outs):")
    print(f"  Origin cluster target %: {origin_target_count / N * 100:.2f}%")
    print(f"  Same origin zone target %: {same_origin_zone_count / N * 100:.2f}%")
    print(f"  Same terminal zone target %: {same_terminal_zone_count / N * 100:.2f}%")
    print(f"  Cross-zone target %: {cross_zone_count / N * 100:.2f}%")

    print("\nPer-Pattern Metrics:")
    for pat, pm in pattern_metrics.items():
        cnt = pm["count"]
        if cnt > 0:
            mean_d = float(np.mean(pm["dists"]))
            med_d = float(np.median(pm["dists"]))
            print(f"  [{pat}] N={cnt} ({cnt/N*100:.1f}%) | Origin={pm['origin_target']/cnt*100:.1f}% | SameTermZone={pm['same_terminal_zone']/cnt*100:.1f}% | SameAnyZone={pm['same_any_account_zone']/cnt*100:.1f}% | MeanDist={mean_d:.2f}km | MedDist={med_d:.2f}km")

    # Prediction-time-safe candidate generation & baselines
    cluster_by_zone = collections.defaultdict(list)
    for c in delhi_clusters:
        cluster_by_zone[c.district].append(c)

    for z in cluster_by_zone:
        cluster_by_zone[z].sort(key=lambda c: (c.risk_score or 0.5, c.atm_count or 0), reverse=True)

    hotspots = sorted(delhi_clusters, key=lambda c: (c.risk_score or 0.5, c.atm_count or 0), reverse=True)
    hotspot_names = [c.cluster_name for c in hotspots]

    k10_hits = 0
    k25_hits = 0
    k60_hits = 0

    rng_baseline = np.random.RandomState(42)
    random_r1 = 0
    random_r3 = 0
    origin_r1 = 0
    term_zone_r1 = 0
    risk_r1 = 0
    safe_combined_r1 = 0
    safe_combined_r3 = 0

    from database.seed.synthetic_generator import FRAUD_TYPE_ZONE_AFFINITY

    for s in eval_samples:
        target = s["target_cluster_name"]
        orig = s["origin_cluster_name"]
        oz = s["origin_zone"]
        tz = s["term_zone"]
        ft = s["fraud_type"]
        favored_zones = FRAUD_TYPE_ZONE_AFFINITY.get(ft, [])

        # Build prediction-time-safe candidate pool using composite heuristics
        score_map = collections.defaultdict(float)
        score_map[orig] += 10.0
        for c in cluster_by_zone.get(oz, []):
            score_map[c.cluster_name] += 5.0 + (c.risk_score or 0.5)
        for c in cluster_by_zone.get(tz, []):
            score_map[c.cluster_name] += 8.0 + (c.risk_score or 0.5)
        for az in ZONE_ADJACENCY.get(tz, []):
            for c in cluster_by_zone.get(az, []):
                score_map[c.cluster_name] += 3.0 + (c.risk_score or 0.5) * 0.5
        for fz in favored_zones:
            for c in cluster_by_zone.get(fz, []):
                score_map[c.cluster_name] += 2.5
        for rank, name in enumerate(hotspot_names):
            score_map[name] += max(0.0, 4.0 - rank * 0.1)

        ranked_cands = sorted(delhi_clusters, key=lambda c: score_map[c.cluster_name], reverse=True)
        cands = [c.cluster_name for c in ranked_cands]

        if target in cands[:10]:
            k10_hits += 1
        if target in cands[:25]:
            k25_hits += 1
        if target in cands[:60]:
            k60_hits += 1

        # 1. Random baseline
        rand_order = list(all_delhi_cluster_names)
        rng_baseline.shuffle(rand_order)
        if rand_order[0] == target:
            random_r1 += 1
        if target in rand_order[:3]:
            random_r3 += 1

        # 2. Origin baseline
        if orig == target:
            origin_r1 += 1

        # 3. Terminal-zone baseline (top risk cluster in terminal zone)
        tz_clusters = cluster_by_zone.get(tz, [])
        if tz_clusters and tz_clusters[0].cluster_name == target:
            term_zone_r1 += 1

        # 4. Historical risk baseline (top overall risk cluster)
        if hotspot_names[0] == target:
            risk_r1 += 1

        # 5. Safe combined heuristic (top 1 and top 3 of composite score)
        if cands[0] == target:
            safe_combined_r1 += 1
        if target in cands[:3]:
            safe_combined_r3 += 1

    print("\n--- CANDIDATE GENERATOR EVALUATION (Prediction-Time Safe) ---")
    print(f"  K=10 Natural Candidate Recall: {k10_hits / N * 100:.2f}% ({k10_hits}/{N})")
    print(f"  K=25 Natural Candidate Recall: {k25_hits / N * 100:.2f}% ({k25_hits}/{N})")
    print(f"  K=60 Diagnostic Recall: {k60_hits / N * 100:.2f}% ({k60_hits}/{N})")

    print("\n--- BASELINE EVALUATIONS (Pre-XGBoost) ---")
    print(f"  Random baseline Recall@1: {random_r1 / N * 100:.2f}%")
    print(f"  Random baseline Recall@3: {random_r3 / N * 100:.2f}%")
    print(f"  Origin baseline Recall@1: {origin_r1 / N * 100:.2f}%")
    print(f"  Terminal-zone baseline Recall@1: {term_zone_r1 / N * 100:.2f}%")
    print(f"  Risk baseline Recall@1: {risk_r1 / N * 100:.2f}%")
    print(f"  Safe combined heuristic Recall@1: {safe_combined_r1 / N * 100:.2f}%")
    print(f"  Safe combined heuristic Recall@3: {safe_combined_r3 / N * 100:.2f}%")

    print("\n--- DELAYED MOVEMENT & SHARED MULES ---")
    delays = []
    for c in complaints:
        c_txns = db.query(Transaction).filter(Transaction.complaint_id == c.id).order_by(Transaction.timestamp).all()
        if c_txns and c.reported_at:
            delta_h = (c_txns[-1].timestamp - c.reported_at).total_seconds() / 3600.0
            delays.append(delta_h)

    delays = np.array(delays)
    delayed_cases = int(np.sum(delays >= 6.0))
    print(f"  Delayed cases (>=6h): {delayed_cases} ({delayed_cases / len(delays) * 100:.2f}%)")
    print(f"  Delay Min: {float(np.min(delays)):.2f}h, Max: {float(np.max(delays)):.2f}h, Median: {float(np.median(delays)):.2f}h")

    ca_counts = Counter(row.account_id for row in db.query(ComplaintAccount.account_id).all())
    counts_list = list(ca_counts.values())
    print(f"  Shared-mule max complaints/account: {np.max(counts_list)}")
    print(f"  Shared-mule median: {np.median(counts_list)}")
    print(f"  Shared-mule p95: {np.percentile(counts_list, 95):.2f}")
    print(f"  Shared-mule p99: {np.percentile(counts_list, 99):.2f}")

    db.close()

if __name__ == "__main__":
    run_analysis()
