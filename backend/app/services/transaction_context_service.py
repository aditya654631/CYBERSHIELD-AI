"""
CyberShield AI — Transaction Context Resolver Service
Phase 1 Step 6: Transaction Scenario Ingestion & Complaint-Context Linking

Provides deterministic, deduplicated, provenance-aware, and restart-stable
transaction context resolution for complaints:
1. DIRECT: Returns direct transactions owned by the complaint.
2. LINKED_SYNTHETIC_SCENARIO: Returns the Step-4 synthetic scenario transaction trail
   linked via Step-5 provenance, preserving original transaction ownership.
3. EMPTY: Returns empty context for unlinked / non-Delhi complaints with zero fake data.

Strictly Read-Only:
- Zero writes to PostgreSQL during retrieval.
- Zero target-label leakage (no inspection of withdrawals, predictions, or ATM targets).
"""

from datetime import datetime, timezone, timedelta
from typing import Dict, Any, List, Optional
from sqlalchemy.orm import Session
from backend.app.models.models import Complaint, Transaction
from backend.app.services.scenario_linking_service import get_scenario_for_complaint
from backend.app.services.prediction_contract import as_utc


def resolve_transaction_context(
    db: Session,
    complaint: Complaint,
    analysis_as_of: Optional[datetime] = None,
    allow_legacy_assumptions: bool = True
) -> Dict[str, Any]:
    """
    Resolves the canonical transaction context for a given complaint strictly as of `analysis_as_of`.

    Guarantees:
    1. Point-in-time causal isolation: Transfers occurring AFTER analysis_as_of are excluded.
    2. Knowledge-time enforcement: Transfers received AFTER analysis_as_of are excluded.
    3. Disclosed legacy assumptions: Historical transactions with unknown received_at are
       assumed known at event time only when allow_legacy_assumptions=True.
    4. Rejects unsupported future analysis cutoffs.

    Returns:
        Dict with keys:
            - complaint_number (str)
            - context_type ("DIRECT" | "LINKED_SYNTHETIC_SCENARIO" | "EMPTY")
            - source_scenario (Optional[str])
            - transactions (List[Transaction], deduplicated and ordered)
            - transaction_count (int)
            - analysis_as_of (datetime)
            - legacy_assumptions_applied (bool)
            - provenance (Optional[str])
    """
    if not complaint:
        return {
            "complaint_number": "",
            "context_type": "EMPTY",
            "source_scenario": None,
            "transactions": [],
            "transaction_count": 0,
            "analysis_as_of": None,
            "legacy_assumptions_applied": False,
            "provenance": None
        }

    now_utc = datetime.now(timezone.utc)
    if analysis_as_of is not None:
        as_of_utc = as_utc(analysis_as_of)
        if as_of_utc and as_of_utc > now_utc + timedelta(minutes=5):
            raise ValueError("Analysis cutoff cannot be set to a future timestamp.")
        effective_cutoff = as_of_utc.replace(tzinfo=None)
    else:
        # Live operational mode (no cutoff specified): use current system time so all known
        # post-report transactions are included in operational analysis.
        effective_cutoff = now_utc.replace(tzinfo=None)

    legacy_assumptions_applied = False

    # 1. DIRECT TRANSACTION RULE:
    # Query transactions owned directly by the complaint up to the effective event-time cutoff.
    direct_candidates = db.query(Transaction).filter(
        Transaction.complaint_id == complaint.id,
        Transaction.timestamp <= effective_cutoff,
    ).order_by(
        Transaction.timestamp.asc(),
        Transaction.id.asc()
    ).all()

    eligible_direct = []
    for tx in direct_candidates:
        # Knowledge-time enforcement
        if tx.received_at is not None:
            tx_rec_utc = as_utc(tx.received_at).replace(tzinfo=None)
            if tx_rec_utc > effective_cutoff:
                # Arrived at system after cutoff: exclude from historical replay!
                continue
            eligible_direct.append(tx)
        else:
            # Legacy transaction with unrecorded knowledge time
            if allow_legacy_assumptions:
                legacy_assumptions_applied = True
                eligible_direct.append(tx)
            else:
                # Strict replay without legacy assumptions excludes unverified timestamps
                continue

    if eligible_direct:
        effective_direct = resolve_effective_transactions(eligible_direct)
        legacy_note = " [Disclosed legacy assumption: event-time knowledge applied for pre-Phase-2 records]" if legacy_assumptions_applied else ""
        return {
            "complaint_number": complaint.complaint_number,
            "context_type": "DIRECT",
            "source_scenario": None,
            "transactions": effective_direct,
            "transaction_count": len(effective_direct),
            "analysis_as_of": effective_cutoff,
            "legacy_assumptions_applied": legacy_assumptions_applied,
            "provenance": (
                f"SYNTHETIC_DEMO: Direct transactions owned by {complaint.complaint_number} as of {effective_cutoff.isoformat()}{legacy_note}"
                if complaint.complaint_number.startswith("CMP-DL-") else
                f"DIRECT_OFFICER_INPUT: Direct transactions owned by {complaint.complaint_number} as of {effective_cutoff.isoformat()}{legacy_note}"
            )
        }

    # 2. LINKED SCENARIO RULE:
    # Resolve persisted Step-5 source scenario without re-running matching.
    scenario = get_scenario_for_complaint(db, complaint)
    if scenario and scenario.id != complaint.id:
        scenario_cutoff = min(effective_cutoff, scenario.reported_at or effective_cutoff)
        scenario_candidates = db.query(Transaction).filter(
            Transaction.complaint_id == scenario.id,
            Transaction.timestamp <= scenario_cutoff,
        ).order_by(
            Transaction.timestamp.asc(),
            Transaction.id.asc()
        ).all()

        eligible_scenario = []
        for tx in scenario_candidates:
            if tx.received_at is not None:
                tx_rec_utc = as_utc(tx.received_at).replace(tzinfo=None)
                if tx_rec_utc > effective_cutoff:
                    continue
                eligible_scenario.append(tx)
            else:
                if allow_legacy_assumptions:
                    legacy_assumptions_applied = True
                    eligible_scenario.append(tx)

        effective_scenario = resolve_effective_transactions(eligible_scenario)
        return {
            "complaint_number": complaint.complaint_number,
            "context_type": "LINKED_SYNTHETIC_SCENARIO",
            "source_scenario": scenario.complaint_number,
            "transactions": effective_scenario,
            "transaction_count": len(effective_scenario),
            "analysis_as_of": effective_cutoff,
            "legacy_assumptions_applied": legacy_assumptions_applied,
            "provenance": f"Synthetic operational scenario context linked from {scenario.complaint_number} as of {effective_cutoff.isoformat()}"
        }

    # 3. EMPTY / UNSUPPORTED RULE:
    return {
        "complaint_number": complaint.complaint_number,
        "context_type": "EMPTY",
        "source_scenario": None,
        "transactions": [],
        "transaction_count": 0,
        "analysis_as_of": effective_cutoff,
        "legacy_assumptions_applied": False,
        "provenance": None
    }


def resolve_effective_transactions(eligible_transactions: List[Transaction]) -> List[Transaction]:
    """
    Computes effective transactions for predictive model input and graph construction:
    1. Preserves every original, correction, and reversal record in PostgreSQL for auditing.
    2. A correction supersedes its referenced original transaction in effective model input.
    3. A reversal cancels its referenced original transaction from effective model input.
    4. Deterministically resolves chained corrections (A -> B -> C: C is the effective state).
    5. Rejects / ignores circular, invalid, or cross-referenced chains.
    6. Knowledge-time rules: Only corrections/reversals with received_at <= cutoff are in eligible_transactions,
       so historical replays before correction received_at continue seeing the original evidence.
    """
    if not eligible_transactions:
        return []

    # Map by transaction_ref
    tx_by_ref: Dict[str, Transaction] = {}
    for tx in eligible_transactions:
        if tx.transaction_ref:
            tx_by_ref[tx.transaction_ref] = tx

    # Build mapping from parent_ref -> list of direct child corrections/reversals
    children_map: Dict[str, List[Transaction]] = {}
    for tx in eligible_transactions:
        parent_ref = tx.correction_of_ref
        if parent_ref and parent_ref in tx_by_ref and parent_ref != tx.transaction_ref:
            children_map.setdefault(parent_ref, []).append(tx)

    # Roots: transactions that are not corrections of any eligible transaction in this set
    roots: List[Transaction] = []
    for tx in eligible_transactions:
        parent_ref = tx.correction_of_ref
        if not parent_ref or parent_ref not in tx_by_ref:
            roots.append(tx)

    effective: List[Transaction] = []
    for root in roots:
        curr = root
        visited = {curr.transaction_ref}
        is_reversed = False

        while curr.transaction_ref in children_map:
            children = [c for c in children_map[curr.transaction_ref] if c.transaction_ref not in visited]
            if not children:
                break
            # Deterministic ordering: latest knowledge/event time, then highest id
            children.sort(key=lambda t: (t.received_at or t.timestamp or datetime.min, t.id or 0))
            next_tx = children[-1]
            visited.add(next_tx.transaction_ref)
            curr = next_tx
            if curr.is_reversal:
                is_reversed = True
                break

        if not is_reversed and not curr.is_reversal:
            effective.append(curr)

    # Sort effective transactions chronologically
    effective.sort(key=lambda t: (t.timestamp or datetime.min, t.id or 0))
    return _deduplicate_transactions(effective)


def _deduplicate_transactions(transactions: List[Transaction]) -> List[Transaction]:
    """
    Deduplicates a list of Transaction records by primary key while preserving order.
    """
    seen_ids = set()
    deduped = []
    for tx in transactions:
        if tx.id not in seen_ids:
            seen_ids.add(tx.id)
            deduped.append(tx)
    return deduped
