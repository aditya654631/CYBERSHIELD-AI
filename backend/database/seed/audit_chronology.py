"""
Comprehensive Pre-V3.1 Training Chronology & Sanity Audit
"""

import numpy as np
from collections import Counter
from decimal import Decimal

from backend.app.models.db import SessionLocal
from backend.app.models.models import (
    Complaint, Transaction, Withdrawal, Account, LocationCluster, ATMLocation
)
from backend.app.services.transaction_context_service import resolve_transaction_context
from backend.app.services.graph_service import build_complaint_graph
from database.seed.synthetic_generator import DelhiSyntheticDataGenerator, ZONE_ADJACENCY
from database.seed.seed_config import SYNTHETIC_RANDOM_SEED, NUM_COMPLAINTS, NUM_ACCOUNTS

def run_audit():
    db = SessionLocal()
    comps = db.query(Complaint).filter(Complaint.complaint_number.like("CMP-DL-%")).all()

    # 1. Trace the -70.62h metric
    # In audit_dataset_v2.py, lines 241-248:
    # delta_h = (c_txns[-1].timestamp - c.reported_at).total_seconds() / 3600.0
    print("======================================================================")
    print("1. TRACING THE -70.62h METRIC")
    print("======================================================================")
    print("Source: database/seed/audit_dataset_v2.py lines 241-248")
    print("Code: delta_h = (c_txns[-1].timestamp - c.reported_at).total_seconds() / 3600.0")
    print("Semantic: FINAL TRANSACTION TIMESTAMP MINUS COMPLAINT REPORTED_AT TIMESTAMP")
    print("A negative value means the last transaction occurred BEFORE the complaint was reported.")
    print("Example: Fraud ended on Jan 1st 12:00, victim reported on Jan 4th 10:37 -> delta = -70.62 hours.")
    print("This was an informal latency offset metric in the scratch script, NOT a reporting delay violation.")

    # 2. Complaint Reporting Delay: reported_at - incident_time
    print("\n======================================================================")
    print("2. COMPLAINT REPORTING DELAY (reported_at - incident_time)")
    print("======================================================================")
    delays_h = []
    neg_count = 0
    zero_count = 0
    for c in comps:
        if c.reported_at and c.incident_time:
            d = (c.reported_at - c.incident_time).total_seconds() / 3600.0
            delays_h.append(d)
            if d < 0:
                neg_count += 1
            elif d == 0:
                zero_count += 1

    delays_h = np.array(delays_h)
    print(f"Total Complaints: {len(delays_h)}")
    print(f"Minimum delay:    {np.min(delays_h):.4f}h")
    print(f"Maximum delay:    {np.max(delays_h):.4f}h")
    print(f"Median delay:     {np.median(delays_h):.4f}h")
    print(f"p01 delay:        {np.percentile(delays_h, 1):.4f}h")
    print(f"p05 delay:        {np.percentile(delays_h, 5):.4f}h")
    print(f"p95 delay:        {np.percentile(delays_h, 95):.4f}h")
    print(f"p99 delay:        {np.percentile(delays_h, 99):.4f}h")
    print(f"Negative count:   {neg_count}")
    print(f"Zero count:       {zero_count}")

    # 3. Transaction Cutoff Validation
    print("\n======================================================================")
    print("3. TRANSACTION CUTOFF VALIDATION")
    print("======================================================================")
    tx_by_comp = {}
    for tx in db.query(Transaction).filter(Transaction.transaction_ref.like("TXN-DL-%")).all():
        tx_by_comp.setdefault(tx.complaint_id, []).append(tx)

    tx_after_report = 0
    for c in comps:
        ctxs = tx_by_comp.get(c.id, [])
        for t in ctxs:
            if c.reported_at and t.timestamp > c.reported_at:
                tx_after_report += 1

    print(f"Total Synthetic Transactions: {sum(len(v) for v in tx_by_comp.values())}")
    print(f"Transactions occurring AFTER complaint reported_at: {tx_after_report}")
    if tx_after_report > 0:
        print(f"  Note: In delayed multi-hop fraud (6h–48h parking), victim reported fraud while money was still moving through downstream hops.")

    # 4. Withdrawal Chronology
    print("\n======================================================================")
    print("4. WITHDRAWAL CHRONOLOGY")
    print("======================================================================")
    # Generate ds in memory to inspect target withdrawals vs final tx
    delhi_clusters = db.query(LocationCluster).filter(LocationCluster.state == "Delhi").all()
    cluster_by_name = {c.cluster_name: c for c in delhi_clusters}
    cluster_dicts = [
        {"name": c.cluster_name, "zone": c.district, "lat": c.center_lat, "lon": c.center_lon, "id": c.id, "risk": c.risk_score or 0.5, "atm_density": c.atm_count or 4}
        for c in delhi_clusters
    ]
    delhi_atms = db.query(ATMLocation).filter(ATMLocation.atm_code.like("ATM-DL-%")).all()
    atm_dicts = [
        {"atm_code": a.atm_code, "bank_name": a.bank_name, "cluster_name": [c["name"] for c in cluster_dicts if c["id"] == a.cluster_id][0], "id": a.id}
        for a in delhi_atms
    ]
    gen = DelhiSyntheticDataGenerator(SYNTHETIC_RANDOM_SEED)
    ds = gen.generate_dataset(cluster_dicts, atm_dicts, NUM_COMPLAINTS, NUM_ACCOUNTS)

    wdl_map = {w["complaint_number"]: w for w in ds["withdrawals"]}
    wdl_before_tx_violations = 0
    wdl_before_report_count = 0
    wdl_after_report_count = 0

    for c in comps:
        w = wdl_map.get(c.complaint_number)
        if not w:
            continue
        w_time = w["timestamp"]
        c_txs = tx_by_comp.get(c.id, [])
        if c_txs:
            max_tx_time = max(t.timestamp for t in c_txs)
            if w_time < max_tx_time:
                wdl_before_tx_violations += 1

        if c.reported_at:
            if w_time < c.reported_at:
                wdl_before_report_count += 1
            else:
                wdl_after_report_count += 1

    print(f"Total Withdrawals: {len(ds['withdrawals'])}")
    print(f"Withdrawals occurring BEFORE final transaction timestamp: {wdl_before_tx_violations}")
    print(f"Withdrawals occurring AFTER complaint reported_at (future cash-outs): {wdl_after_report_count} ({wdl_after_report_count / len(ds['withdrawals']) * 100:.2f}%)")
    print(f"Withdrawals occurring BEFORE complaint reported_at (historical cash-outs): {wdl_before_report_count} ({wdl_before_report_count / len(ds['withdrawals']) * 100:.2f}%)")

    # 5. Delayed Movement Metric (Step-4 / Rule 36)
    print("\n======================================================================")
    print("5. DELAYED MOVEMENT METRIC (Rule 36)")
    print("======================================================================")
    inter_tx_diffs_h = []
    delayed_cases = 0
    for cid, ctxs in tx_by_comp.items():
        if len(ctxs) > 1:
            st = sorted(ctxs, key=lambda x: x.timestamp)
            diffs = [(st[i+1].timestamp - st[i].timestamp).total_seconds() / 3600.0 for i in range(len(st)-1)]
            inter_tx_diffs_h.extend(diffs)
            if any(d >= 6.0 for d in diffs):
                delayed_cases += 1

    inter_tx_diffs_h = np.array(inter_tx_diffs_h)
    print("Definition: Inter-transaction hop delay between consecutive transfers within multi-hop graph")
    print(f"Min hop delay:    {np.min(inter_tx_diffs_h):.4f}h ({np.min(inter_tx_diffs_h)*60:.1f}m)")
    print(f"Max hop delay:    {np.max(inter_tx_diffs_h):.4f}h")
    print(f"Median hop delay: {np.median(inter_tx_diffs_h):.4f}h ({np.median(inter_tx_diffs_h)*60:.1f}m)")
    print(f"Delayed cases (>=6h): {delayed_cases} ({delayed_cases / len(comps) * 100:.2f}%)")

    # 6. Re-verify Live Complaints
    print("\n======================================================================")
    print("6. LIVE COMPLAINT PROVENANCE AUDIT")
    print("======================================================================")
    for cnum in ["CMP-NEW-000002", "CMP-NEW-000003", "CMP-NEW-000004", "CMP-1042"]:
        c = db.query(Complaint).filter(Complaint.complaint_number == cnum).first()
        if not c:
            print(f"  {cnum}: NOT FOUND")
            continue
        ctx = resolve_transaction_context(db, c)
        g = build_complaint_graph(db, c.id)
        m = g.get("metrics", {})
        print(f"  {cnum}:")
        print(f"    exists: True")
        print(f"    source_scenario: {ctx.get('source_scenario')}")
        print(f"    context_type: {ctx.get('context_type')}")
        print(f"    transaction_count: {ctx.get('transaction_count')}")
        print(f"    graph_node_count: {m.get('node_count')}")
        print(f"    graph_edge_count: {m.get('edge_count')}")

    db.close()

if __name__ == "__main__":
    run_audit()
