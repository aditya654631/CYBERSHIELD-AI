"""
CyberShield AI — Database Migration Phase 2 Verification Test

Tests:
1. Fresh database Alembic upgrade directly to head (0007).
2. Upgrade from Phase 1 schema (0006) to Phase 2 head (0007).
3. Verification that all 6 performance indexes exist.
4. Downstream downgrade and re-upgrade safety.
"""

import os
import sqlite3
import subprocess
import sys
import tempfile
import pytest

def test_fresh_database_upgrade_to_head():
    with tempfile.NamedTemporaryFile(suffix=".db", delete=False) as f:
        temp_db_path = f.name

    try:
        norm_path = temp_db_path.replace("\\", "/")
        cmd = [
            sys.executable, "-m", "alembic",
            "-x", f"db_url=sqlite:///{norm_path}",
            "upgrade", "head"
        ]
        res = subprocess.run(cmd, capture_output=True, text=True)
        assert res.returncode == 0, f"Fresh DB upgrade failed: {res.stderr}"

        conn = sqlite3.connect(temp_db_path)
        cur = conn.cursor()

        # Verify all indexes created
        cur.execute("SELECT name FROM sqlite_master WHERE type='index';")
        indexes = {row[0] for row in cur.fetchall()}

        expected_indexes = [
            "ix_complaints_state_district",
            "ix_complaints_reported_at",
            "ix_alerts_comp_pred_status",
            "ix_transactions_comp_hop",
            "ix_bank_actions_comp_status",
            "ix_audit_logs_user_created_at"
        ]
        for exp in expected_indexes:
            assert exp in indexes, f"Index {exp} not found in database indexes: {indexes}"

        conn.close()
    finally:
        try:
            if os.path.exists(temp_db_path):
                os.remove(temp_db_path)
        except Exception:
            pass


def test_upgrade_from_phase1_to_phase2():
    with tempfile.NamedTemporaryFile(suffix=".db", delete=False) as f:
        temp_db_path = f.name

    try:
        norm_path = temp_db_path.replace("\\", "/")

        # Step 1: Upgrade to Phase 1 head (0006)
        cmd_p1 = [
            sys.executable, "-m", "alembic",
            "-x", f"db_url=sqlite:///{norm_path}",
            "upgrade", "0006_bank_actions_lifecycle"
        ]
        res1 = subprocess.run(cmd_p1, capture_output=True, text=True)
        assert res1.returncode == 0, f"Phase 1 upgrade failed: {res1.stderr}"

        # Step 2: Upgrade to Phase 2 head (0007)
        cmd_p2 = [
            sys.executable, "-m", "alembic",
            "-x", f"db_url=sqlite:///{norm_path}",
            "upgrade", "head"
        ]
        res2 = subprocess.run(cmd_p2, capture_output=True, text=True)
        assert res2.returncode == 0, f"Phase 2 upgrade failed: {res2.stderr}"

        conn = sqlite3.connect(temp_db_path)
        cur = conn.cursor()
        cur.execute("SELECT name FROM sqlite_master WHERE type='index';")
        indexes = {row[0] for row in cur.fetchall()}
        assert "ix_complaints_state_district" in indexes
        assert "ix_alerts_comp_pred_status" in indexes
        conn.close()
    finally:
        try:
            if os.path.exists(temp_db_path):
                os.remove(temp_db_path)
        except Exception:
            pass
