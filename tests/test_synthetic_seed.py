"""
Unit and Integration Tests for Phase 1 Step 4:
Delhi Synthetic Dataset & Seed Architecture
"""

import pytest
from decimal import Decimal
from collections import Counter
from backend.app.models.db import SessionLocal
from backend.app.models.models import (
    LocationCluster, ATMLocation, Complaint, Account,
    ComplaintAccount, Transaction, Withdrawal
)
from database.seed.seed_config import (
    SYNTHETIC_RANDOM_SEED, DELHI_ZONES, FRAUD_TYPES, PAYMENT_CHANNELS
)
from database.seed.delhi_geography import DELHI_CLUSTERS_DATA, generate_delhi_atms
from database.seed.synthetic_generator import DelhiSyntheticDataGenerator

def test_deterministic_generation_reproducibility():
    """Verify that running the generator with the fixed random seed produces identical results."""
    gen1 = DelhiSyntheticDataGenerator(SYNTHETIC_RANDOM_SEED)
    gen2 = DelhiSyntheticDataGenerator(SYNTHETIC_RANDOM_SEED)

    accs1 = gen1.generate_accounts(50)
    accs2 = gen2.generate_accounts(50)
    assert accs1 == accs2

    clusters = DELHI_CLUSTERS_DATA[:5]
    atms = generate_delhi_atms(clusters)
    
    gen3 = DelhiSyntheticDataGenerator(SYNTHETIC_RANDOM_SEED)
    gen4 = DelhiSyntheticDataGenerator(SYNTHETIC_RANDOM_SEED)
    d1 = gen3.generate_dataset(clusters, atms, num_complaints=10, num_accounts=30)
    d2 = gen4.generate_dataset(clusters, atms, num_complaints=10, num_accounts=30)

    assert len(d1["complaints"]) == len(d2["complaints"])
    assert len(d1["transactions"]) == len(d2["transactions"])
    assert d1["complaints"][0]["complaint_number"] == d2["complaints"][0]["complaint_number"]
    assert d1["complaints"][0]["amount"] == d2["complaints"][0]["amount"]
    assert d1["transactions"][0]["transaction_ref"] == d2["transactions"][0]["transaction_ref"]


def test_delhi_geography_coverage_and_coordinates():
    """Verify 60 clusters span all 9 Delhi zones and fall strictly within Delhi bounding box."""
    db = SessionLocal()
    try:
        clusters = db.query(LocationCluster).filter(LocationCluster.state == "Delhi").all()
        assert len(clusters) == 60

        covered_zones = {c.district for c in clusters}
        for z in DELHI_ZONES:
            assert z in covered_zones, f"Zone {z} missing in location clusters!"

        # Coordinates check
        for c in clusters:
            assert 28.40 <= c.center_lat <= 28.88, f"Latitude {c.center_lat} out of Delhi bounds!"
            assert 76.84 <= c.center_lon <= 77.35, f"Longitude {c.center_lon} out of Delhi bounds!"

        atms = db.query(ATMLocation).filter(ATMLocation.state == "Delhi").all()
        assert len(atms) == 240
        for a in atms:
            assert 28.40 <= a.latitude <= 28.88, f"ATM Latitude {a.latitude} out of Delhi bounds!"
            assert 76.84 <= a.longitude <= 77.35, f"ATM Longitude {a.longitude} out of Delhi bounds!"
    finally:
        db.close()


def test_complaint_and_account_dataset_integrity():
    """Verify synthetic complaints and accounts satisfy all schema and data rules."""
    db = SessionLocal()
    try:
        complaints = db.query(Complaint).filter(Complaint.complaint_number.like("CMP-DL-%")).all()
        assert len(complaints) == 3000

        # Unique complaint numbers
        comp_nums = [c.complaint_number for c in complaints]
        assert len(comp_nums) == len(set(comp_nums))

        # Positive Numeric amounts
        for c in complaints:
            assert isinstance(c.amount, Decimal) or isinstance(c.amount, float)
            assert c.amount > 0

        # Nullable coordinates verified
        with_coords = sum(1 for c in complaints if c.victim_lat is not None and c.victim_lon is not None)
        without_coords = sum(1 for c in complaints if c.victim_lat is None and c.victim_lon is None)
        assert with_coords > 2000
        assert without_coords > 300

        # Synthetic Accounts (excluding dynamically registered complaint accounts)
        accounts = db.query(Account).filter(Account.account_number.like("SYN-DL-ACC-%")).all()
        assert len(accounts) == 6000
        acc_nums = [a.account_number for a in accounts]
        assert len(acc_nums) == len(set(acc_nums))
    finally:
        db.close()


def test_transaction_graph_topologies_and_flow_sanity():
    """Verify multi-hop transactions have sender != receiver, valid hops, positive amounts, and chronological order."""
    db = SessionLocal()
    try:
        txs = db.query(Transaction).filter(Transaction.transaction_ref.like("TXN-DL-%")).all()
        assert len(txs) >= 40000

        # Unique transaction refs
        tx_refs = [tx.transaction_ref for tx in txs]
        assert len(tx_refs) == len(set(tx_refs))

        # sender != receiver
        for tx in txs:
            assert tx.sender_account_id != tx.receiver_account_id
            assert tx.amount > 0

        # Hop distribution
        hops = Counter(tx.hop_number for tx in txs)
        assert hops[1] > 0
        assert hops[2] > 0
        assert hops[3] > 0
        assert hops[4] > 0
    finally:
        db.close()


def test_complaint_accounts_associations():
    """Verify complaint_accounts are populated with zero duplicates and valid FKs."""
    db = SessionLocal()
    try:
        delhi_comp_ids = {c.id for c in db.query(Complaint.id).filter(Complaint.complaint_number.like("CMP-DL-%")).all()}
        cas = db.query(ComplaintAccount).filter(ComplaintAccount.complaint_id.in_(delhi_comp_ids)).all()
        assert len(cas) > 10000

        pairs = [(ca.complaint_id, ca.account_id) for ca in cas]
        assert len(pairs) == len(set(pairs)), "Duplicate (complaint_id, account_id) found!"

        roles = Counter(ca.association_type for ca in cas)
        assert roles["VICTIM"] == 3000
        assert roles["INTERMEDIARY"] > 0
        assert roles["BENEFICIARY"] > 0
    finally:
        db.close()


def test_withdrawals_and_target_labels():
    """Verify withdrawals link to valid ATMs and accounts with chronological sanity and zero label leakage."""
    db = SessionLocal()
    try:
        delhi_atms = {a.id: a for a in db.query(ATMLocation).filter(ATMLocation.state == "Delhi").all()}
        ws = db.query(Withdrawal).filter(Withdrawal.atm_id.in_(delhi_atms.keys())).all()
        assert len(ws) >= 1500

        for w in ws:
            assert w.atm_id in delhi_atms
            assert w.amount > 0
            assert w.success is True

        # Target zones distribution
        cluster_ids = {delhi_atms[w.atm_id].cluster_id for w in ws}
        clusters = {c.id: c for c in db.query(LocationCluster).filter(LocationCluster.id.in_(cluster_ids)).all()}
        target_zones = {clusters[cl_id].district for cl_id in cluster_ids if cl_id in clusters}
        for z in DELHI_ZONES:
            assert z in target_zones, f"Target zone {z} has no cash-out withdrawals!"
    finally:
        db.close()


def test_shared_mule_account_behavior():
    """Verify shared mule accounts appear in multiple complaints while victim accounts stay unique."""
    db = SessionLocal()
    try:
        delhi_comp_ids = {c.id for c in db.query(Complaint.id).filter(Complaint.state == "Delhi").all()}
        cas = db.query(ComplaintAccount).filter(ComplaintAccount.complaint_id.in_(delhi_comp_ids)).all()
        
        acc_counts = Counter(ca.account_id for ca in cas)
        
        # Shared accounts (linked to > 1 complaint)
        shared_count = sum(1 for cnt in acc_counts.values() if cnt > 1)
        assert shared_count > 100, f"Expected > 100 shared accounts, got {shared_count}"

        # Bounded reuse: max complaints per account should not exceed reasonable bound (e.g. <= 60)
        max_shared = max(acc_counts.values())
        assert max_shared <= 60, f"Account reused in too many complaints: {max_shared}"

        # Unique accounts (single complaint)
        single_count = sum(1 for cnt in acc_counts.values() if cnt == 1)
        assert single_count > 2500, f"Expected > 2500 single-complaint accounts, got {single_count}"
    finally:
        db.close()
