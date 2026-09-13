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

from typing import Dict, Any, List, Optional
from sqlalchemy.orm import Session
from backend.app.models.models import Complaint, Transaction
from backend.app.services.scenario_linking_service import get_scenario_for_complaint


def resolve_transaction_context(
    db: Session,
    complaint: Complaint
) -> Dict[str, Any]:
    """
    Resolves the canonical transaction context for a given complaint.

    Returns:
        Dict with keys:
            - complaint_number (str)
            - context_type ("DIRECT" | "LINKED_SYNTHETIC_SCENARIO" | "EMPTY")
            - source_scenario (Optional[str])
            - transactions (List[Transaction], deduplicated and ordered)
            - transaction_count (int)
            - provenance (Optional[str])
    """
    if not complaint:
        return {
            "complaint_number": "",
            "context_type": "EMPTY",
            "source_scenario": None,
            "transactions": [],
            "transaction_count": 0,
            "provenance": None
        }

    # 1. DIRECT TRANSACTION RULE:
    # First check whether the requested complaint genuinely owns direct Transaction rows.
    direct_query = db.query(Transaction).filter(
        Transaction.complaint_id == complaint.id,
        Transaction.timestamp <= complaint.reported_at,
    ).order_by(
        Transaction.timestamp.asc(),
        Transaction.id.asc()
    ).all()

    if direct_query:
        deduped_direct = _deduplicate_transactions(direct_query)
        return {
            "complaint_number": complaint.complaint_number,
            "context_type": "DIRECT",
            "source_scenario": None,
            "transactions": deduped_direct,
            "transaction_count": len(deduped_direct),
            "provenance": (
                f"SYNTHETIC_DEMO: Pre-report transactions owned by {complaint.complaint_number}"
                if complaint.complaint_number.startswith("CMP-DL-") else
                f"DIRECT_OFFICER_INPUT: Pre-report transactions owned by complaint {complaint.complaint_number}"
            )
        }

    # 2. LINKED SCENARIO RULE:
    # Resolve persisted Step-5 source scenario without re-running matching.
    scenario = get_scenario_for_complaint(db, complaint)
    if scenario and scenario.id != complaint.id:
        scenario_query = db.query(Transaction).filter(
            Transaction.complaint_id == scenario.id,
            Transaction.timestamp <= scenario.reported_at,
        ).order_by(
            Transaction.timestamp.asc(),
            Transaction.id.asc()
        ).all()

        deduped_scenario = _deduplicate_transactions(scenario_query)
        return {
            "complaint_number": complaint.complaint_number,
            "context_type": "LINKED_SYNTHETIC_SCENARIO",
            "source_scenario": scenario.complaint_number,
            "transactions": deduped_scenario,
            "transaction_count": len(deduped_scenario),
            "provenance": f"Synthetic operational scenario context linked from {scenario.complaint_number}"
        }

    # 3. EMPTY / UNSUPPORTED RULE:
    # Non-Delhi, unlinked, or no valid persisted scenario.
    # Zero fake data, zero fallback to CMP-1042.
    return {
        "complaint_number": complaint.complaint_number,
        "context_type": "EMPTY",
        "source_scenario": None,
        "transactions": [],
        "transaction_count": 0,
        "provenance": None
    }


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
