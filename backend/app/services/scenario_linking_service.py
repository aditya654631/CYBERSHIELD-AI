"""
CyberShield AI — Complaint-to-Scenario Linking Service
Phase 1 Step 5: Deterministic, explainable scenario matching and account linking
with strict zero target-label leakage and full transaction trail accessibility.
"""

import re
from typing import Optional, Tuple, Dict, Any, List
from sqlalchemy.orm import Session
from sqlalchemy import func
from backend.app.models.models import Complaint, Account, ComplaintAccount, Transaction

# Allowed amount band classifications for pre-prediction matching
AMOUNT_BANDS = [
    ("MICRO", 0.0, 25000.0),
    ("SMALL", 25000.0, 100000.0),
    ("MEDIUM", 100000.0, 500000.0),
    ("LARGE", 500000.0, 2000000.0),
    ("MAJOR", 2000000.0, float("inf")),
]

def get_amount_band(amount: float) -> str:
    for band_name, low, high in AMOUNT_BANDS:
        if low <= amount < high:
            return band_name
    return "MAJOR"

def get_band_index(band: str) -> int:
    for idx, (b_name, _, _) in enumerate(AMOUNT_BANDS):
        if b_name == band:
            return idx
    return 0

def match_scenario(db: Session, complaint: Complaint) -> Tuple[Optional[Complaint], str, float]:
    """
    Deterministically matches a complaint to an eligible Step-4 Delhi operational scenario.
    
    STRICT ZERO TARGET-LEAKAGE GUARANTEE:
    This function ONLY inspects pre-prediction complaint dimensions:
    - state
    - district / operational zone
    - fraud_type
    - payment_channel
    - amount band & numerical proximity
    - reporting delay / incident time (if available)
    
    It STRICTLY EXCLUDES all post-incident ground truth:
    - No withdrawal checks
    - No ATM target checks
    - No cashout cluster checks
    - No ML prediction checks
    """
    # 1. State / Jurisdiction Check
    if not complaint.state or complaint.state.strip().lower() != "delhi":
        return None, "SCENARIO_UNAVAILABLE", 0.0

    # 2. Minimum Input Sufficiency Check
    if not complaint.amount or complaint.amount <= 0 or not complaint.fraud_type:
        return None, "INSUFFICIENT_SCENARIO_INPUT", 0.0

    comp_district = (complaint.district or "").strip().upper()
    comp_fraud = (complaint.fraud_type or "").strip().lower()
    comp_channel = (complaint.payment_channel or "").strip().upper()
    comp_amt = float(complaint.amount)
    comp_band = get_amount_band(comp_amt)
    comp_band_idx = get_band_index(comp_band)

    # 3. Retrieve Delhi Synthetic Scenario Library (CMP-DL-%)
    candidates = db.query(Complaint).filter(
        Complaint.complaint_number.like("CMP-DL-%"),
        Complaint.state == "Delhi"
    ).all()

    if not candidates:
        return None, "SCENARIO_UNAVAILABLE", 0.0

    # 4. Multi-dimensional deterministic scoring
    scored_candidates = []
    for cand in candidates:
        cand_district = (cand.district or "").strip().upper()
        cand_fraud = (cand.fraud_type or "").strip().lower()
        cand_channel = (cand.payment_channel or "").strip().upper()
        cand_amt = float(cand.amount)
        cand_band = get_amount_band(cand_amt)
        cand_band_idx = get_band_index(cand_band)

        score = 0.0
        same_zone = (cand_district == comp_district)
        same_fraud = (cand_fraud == comp_fraud)
        same_channel = (cand_channel == comp_channel)
        same_band = (cand_band == comp_band)

        # Dimension weights
        if same_zone:
            score += 30.0
        if same_fraud:
            score += 25.0
        if same_channel:
            score += 20.0
        if same_band:
            score += 15.0
        elif abs(cand_band_idx - comp_band_idx) == 1:
            score += 5.0  # Adjacent amount band

        # Amount proximity fine-tuning (up to 5.0 points)
        rel_diff = abs(cand_amt - comp_amt) / max(comp_amt, 1.0)
        score += max(0.0, 5.0 * (1.0 - min(rel_diff, 1.0)))

        # Categorize into priority tiers
        if same_zone and same_fraud and same_channel and same_band:
            tier = "Tier 1: Same Zone, Fraud Type, Channel, Amount Band"
        elif same_zone and same_fraud and (same_channel or same_band):
            tier = "Tier 2: Same Zone, Fraud Type, Similar Profile"
        elif same_zone and (same_channel or same_band):
            tier = "Tier 3: Same Zone, Channel/Amount Similar"
        elif same_zone:
            tier = "Tier 4: Same Delhi Zone General Match"
        else:
            tier = "Tier 5: Cross-Zone Fallback Match"

        scored_candidates.append((score, tier, cand))

    # Equal financial/geographic evidence must produce equal matches across
    # restarts, independent of the victim's identity or Python hash seed.
    def sort_key(item):
        score, _, cand = item
        return (-score, cand.complaint_number)

    scored_candidates.sort(key=sort_key)
    best_score, best_tier, best_scenario = scored_candidates[0]

    return best_scenario, best_tier, round(best_score, 2)


def link_complaint_to_scenario(db: Session, complaint: Complaint) -> Dict[str, Any]:
    """
    Matches and links an incoming complaint to an existing synthetic scenario.
    Populates ComplaintAccount records for all accounts in the scenario.
    Records provenance metadata cleanly in the complaint description.
    """
    # 0. DIRECT TRANSACTION PRECEDENCE CHECK:
    # If direct transactions already exist on this complaint, preserve them. Do not overwrite with synthetic accounts.
    direct_txs = db.query(Transaction).filter(Transaction.complaint_id == complaint.id).all()
    if direct_txs:
        direct_cas = db.query(ComplaintAccount).filter(ComplaintAccount.complaint_id == complaint.id).all()
        complaint.provenance_mode = "DIRECT_OFFICER_INPUT"
        db.flush()
        return {
            "status": "DIRECT_OFFICER_INPUT",
            "source_scenario": None,
            "match_reason": "Direct complaint transaction context takes precedence",
            "match_score": 0.0,
            "linked_account_count": len(direct_cas),
            "available_transaction_count": len(direct_txs)
        }

    scenario, tier_reason, score = match_scenario(db, complaint)
    if scenario is None:
        return {
            "status": tier_reason,
            "source_scenario": None,
            "match_reason": tier_reason,
            "match_score": 0.0,
            "linked_account_count": 0,
            "available_transaction_count": 0
        }

    # 1. Retrieve all accounts associated with source scenario
    source_cas = db.query(ComplaintAccount).filter(
        ComplaintAccount.complaint_id == scenario.id
    ).all()

    # 2. Establish ComplaintAccount associations for the new complaint
    new_cas = []
    for sca in source_cas:
        # Prevent duplicates
        existing = db.query(ComplaintAccount).filter(
            ComplaintAccount.complaint_id == complaint.id,
            ComplaintAccount.account_id == sca.account_id
        ).first()
        if not existing:
            new_cas.append(ComplaintAccount(
                complaint_id=complaint.id,
                account_id=sca.account_id,
                association_type=sca.association_type
            ))

    if new_cas:
        db.add_all(new_cas)
        db.flush()

    # 3. Determine transaction count from source scenario
    tx_count = db.query(Transaction).filter(
        Transaction.complaint_id == scenario.id
    ).count()

    # 4. Record scenario provenance in complaint description
    provenance_tag = f"[SCENARIO:{scenario.complaint_number}|STATUS:LINKED|SCORE:{score:.1f}|REASON:{tier_reason}]"
    complaint.provenance_mode = "LINKED_SYNTHETIC_SCENARIO"
    if complaint.description:
        if "[SCENARIO:" not in complaint.description:
            complaint.description = f"{provenance_tag}\n{complaint.description}"
    else:
        complaint.description = provenance_tag

    db.flush()

    return {
        "status": "LINKED",
        "source_scenario": scenario.complaint_number,
        "match_reason": tier_reason,
        "match_score": score,
        "linked_account_count": len(source_cas),
        "available_transaction_count": tx_count
    }


def get_scenario_for_complaint(db: Session, complaint: Complaint) -> Optional[Complaint]:
    """Resolves the source synthetic scenario for a given complaint."""
    if not complaint:
        return None

    # Check if this complaint IS a synthetic scenario itself
    if complaint.complaint_number.startswith("CMP-DL-"):
        return complaint

    # Only an explicitly persisted demo link can authorize borrowed context.
    # Officer narrative text and a shared account cannot establish a scenario.
    if complaint.provenance_mode != "LINKED_SYNTHETIC_SCENARIO":
        return None
    if complaint.description:
        match = re.search(r"\[SCENARIO:(CMP-DL-\d+)\|", complaint.description)
        if match:
            scenario_num = match.group(1)
            sc = db.query(Complaint).filter(Complaint.complaint_number == scenario_num).first()
            if sc:
                return sc

    return None


def get_transactions_for_complaint(db: Session, complaint: Complaint) -> List[Transaction]:
    """
    Returns the transaction trail for a complaint.
    If direct transactions exist on the complaint, returns them.
    Otherwise, resolves and returns the linked scenario's transactions.
    """
    if not complaint:
        return []

    # 1. Direct transactions
    direct_txs = db.query(Transaction).filter(
        Transaction.complaint_id == complaint.id,
        Transaction.timestamp <= complaint.reported_at,
    ).order_by(Transaction.timestamp, Transaction.id).all()
    if direct_txs:
        return direct_txs

    # 2. Scenario-linked transactions
    scenario = get_scenario_for_complaint(db, complaint)
    if scenario and scenario.id != complaint.id:
        return db.query(Transaction).filter(
            Transaction.complaint_id == scenario.id,
            Transaction.timestamp <= scenario.reported_at,
        ).order_by(Transaction.timestamp, Transaction.id).all()

    return []
