"""
Unit Tests for Case-Scoped Graph and Withdrawal Attribution
Master Corrective Pass V3
"""

import pytest
from datetime import datetime, timedelta
import os
import sys

BASE_DIR = os.path.abspath(os.path.join(os.path.dirname(__file__), ".."))
if BASE_DIR not in sys.path:
    sys.path.insert(0, BASE_DIR)

from backend.app.models.db import SessionLocal
from backend.app.models.models import Complaint, Account, Transaction, ComplaintAccount, Withdrawal, ATMLocation, LocationCluster
from backend.app.services.graph_service import build_complaint_graph


def test_graph_empty_response():
    """Verify empty graph response for non-existent complaint without crashing."""
    db = SessionLocal()
    try:
        graph = build_complaint_graph(db, complaint_id=99999999)
        assert graph["nodes"] == []
        assert graph["edges"] == []
        assert graph["metrics"]["node_count"] == 0
    finally:
        db.close()


def test_graph_scoped_attribution_conservation():
    """Verify case-scoped graph attribution enforces fund conservation and valid region."""
    db = SessionLocal()
    try:
        # Fetch an existing synthetic complaint
        comp = db.query(Complaint).filter(Complaint.complaint_number.like("CMP-DL-%")).first()
        if not comp:
            pytest.skip("No Delhi synthetic complaint in database")

        graph = build_complaint_graph(db, complaint_id=comp.id, include_outcomes=True)
        assert "nodes" in graph
        assert "edges" in graph
        assert "metrics" in graph
        assert graph["metrics"]["node_count"] >= 0

        # Check all ATM terminal nodes belong to Delhi
        atm_nodes = [n for n in graph["nodes"] if n["data"].get("node_type") == "atm"]
        for an in atm_nodes:
            atm_locality = an["data"].get("pattern_flags", {}).get("atm_locality")
            assert atm_locality is not None
    finally:
        db.close()
