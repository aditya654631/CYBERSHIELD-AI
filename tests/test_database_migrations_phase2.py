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
            "ix_audit_logs_user_created_at",
            "ix_predictions_comp_version",
            "ix_predictions_comp_input_fp",
            "ix_transactions_received_at",
        ]
        for exp in expected_indexes:
            assert exp in indexes, f"Index {exp} not found in database indexes: {indexes}"

        # Verify new columns on predictions and transactions
        cur.execute("PRAGMA table_info(predictions);")
        pred_cols = {row[1] for row in cur.fetchall()}
        assert "version_number" in pred_cols
        assert "parent_prediction_id" in pred_cols
        assert "analysis_as_of" in pred_cols
        assert "input_fingerprint" in pred_cols

        cur.execute("PRAGMA table_info(transactions);")
        tx_cols = {row[1] for row in cur.fetchall()}
        assert "received_at" in tx_cols
        assert "source_system" in tx_cols
        assert "dedup_key" in tx_cols
        assert "is_reversal" in tx_cols
        assert "correction_of_ref" in tx_cols

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


def test_upgrade_from_populated_0008_to_0009():
    """
    Test upgrading an existing database populated with Phase 1 data (up to 0008)
    to Phase 2 (0009):
    1. Historical predictions without version numbers are deterministically backfilled 1..N.
    2. Parent prediction IDs are properly chained.
    3. Strict uniqueness constraint on (complaint_id, version_number) is enforced.
    4. New transaction columns (analysis_status, prediction_id) exist.
    """
    with tempfile.NamedTemporaryFile(suffix=".db", delete=False) as f:
        temp_db_path = f.name

    try:
        norm_path = temp_db_path.replace("\\", "/")

        # 1. Upgrade to 0008_prediction_snapshots
        cmd_p1 = [
            sys.executable, "-m", "alembic",
            "-x", f"db_url=sqlite:///{norm_path}",
            "upgrade", "0008_prediction_snapshots"
        ]
        res1 = subprocess.run(cmd_p1, capture_output=True, text=True)
        assert res1.returncode == 0, f"0008 upgrade failed: {res1.stderr}"

        # 2. Seed populated data into 0008 schema
        conn = sqlite3.connect(temp_db_path)
        cur = conn.cursor()

        # Seed 2 complaints
        cur.execute("""
            INSERT INTO complaints (complaint_number, fraud_type, amount, victim_location, case_status, state, district, created_at)
            VALUES ('CMP-POP-01', 'UPI_FRAUD', 50000.0, 'Connaught Place, Delhi', 'ACTIVE', 'Delhi', 'CENTRAL_NEW_DELHI', '2026-09-01 10:00:00')
        """)
        c1_id = cur.lastrowid

        cur.execute("""
            INSERT INTO complaints (complaint_number, fraud_type, amount, victim_location, case_status, state, district, created_at)
            VALUES ('CMP-POP-02', 'IMPS_FRAUD', 75000.0, 'Saket, Delhi', 'ACTIVE', 'Delhi', 'SOUTH_DELHI', '2026-09-02 11:00:00')
        """)
        c2_id = cur.lastrowid

        # Seed 3 historical predictions for complaint 1
        cur.execute("""
            INSERT INTO predictions (complaint_id, predicted_window_start, predicted_window_end, window_label, created_at)
            VALUES (?, '2026-09-01 12:00:00', '2026-09-01 14:00:00', 'Next 2–4 Hours', '2026-09-01 10:05:00')
        """, (c1_id,))
        p1_1 = cur.lastrowid

        cur.execute("""
            INSERT INTO predictions (complaint_id, predicted_window_start, predicted_window_end, window_label, created_at)
            VALUES (?, '2026-09-01 12:30:00', '2026-09-01 14:30:00', 'Next 2–4 Hours', '2026-09-01 10:30:00')
        """, (c1_id,))
        p1_2 = cur.lastrowid

        cur.execute("""
            INSERT INTO predictions (complaint_id, predicted_window_start, predicted_window_end, window_label, created_at)
            VALUES (?, '2026-09-01 13:00:00', '2026-09-01 15:00:00', 'Next 2–4 Hours', '2026-09-01 11:00:00')
        """, (c1_id,))
        p1_3 = cur.lastrowid

        # Seed 2 historical predictions for complaint 2
        cur.execute("""
            INSERT INTO predictions (complaint_id, predicted_window_start, predicted_window_end, window_label, created_at)
            VALUES (?, '2026-09-02 13:00:00', '2026-09-02 15:00:00', 'Next 2–4 Hours', '2026-09-02 11:15:00')
        """, (c2_id,))
        p2_1 = cur.lastrowid

        cur.execute("""
            INSERT INTO predictions (complaint_id, predicted_window_start, predicted_window_end, window_label, created_at)
            VALUES (?, '2026-09-02 14:00:00', '2026-09-02 16:00:00', 'Next 2–4 Hours', '2026-09-02 12:00:00')
        """, (c2_id,))
        p2_2 = cur.lastrowid

        conn.commit()
        conn.close()

        # 3. Upgrade to 0009 (head)
        cmd_p2 = [
            sys.executable, "-m", "alembic",
            "-x", f"db_url=sqlite:///{norm_path}",
            "upgrade", "head"
        ]
        res2 = subprocess.run(cmd_p2, capture_output=True, text=True)
        assert res2.returncode == 0, f"0009 upgrade with populated data failed: {res2.stderr}"

        # 4. Verify backfilled versions and chaining
        conn = sqlite3.connect(temp_db_path)
        cur = conn.cursor()

        cur.execute("SELECT id, version_number, parent_prediction_id FROM predictions WHERE complaint_id = ? ORDER BY id ASC", (c1_id,))
        c1_preds = cur.fetchall()
        assert len(c1_preds) == 3
        # Check v1
        assert c1_preds[0] == (p1_1, 1, None), f"Expected v1 parent None, got {c1_preds[0]}"
        # Check v2
        assert c1_preds[1] == (p1_2, 2, p1_1), f"Expected v2 parent {p1_1}, got {c1_preds[1]}"
        # Check v3
        assert c1_preds[2] == (p1_3, 3, p1_2), f"Expected v3 parent {p1_2}, got {c1_preds[2]}"

        cur.execute("SELECT id, version_number, parent_prediction_id FROM predictions WHERE complaint_id = ? ORDER BY id ASC", (c2_id,))
        c2_preds = cur.fetchall()
        assert len(c2_preds) == 2
        assert c2_preds[0] == (p2_1, 1, None)
        assert c2_preds[1] == (p2_2, 2, p2_1)

        # 5. Verify new columns on transactions
        cur.execute("PRAGMA table_info(transactions);")
        tx_cols = {row[1] for row in cur.fetchall()}
        assert "analysis_status" in tx_cols
        assert "prediction_id" in tx_cols

        # 6. Verify strict uniqueness on (complaint_id, version_number)
        cur.execute("PRAGMA index_list(predictions);")
        indexes = {row[1]: row[2] for row in cur.fetchall()}  # name: unique (1 or 0)
        assert "ix_predictions_comp_version" in indexes
        assert indexes["ix_predictions_comp_version"] == 1, "Index ix_predictions_comp_version must be unique"

        # Attempt inserting a duplicate (complaint_id, version_number) to ensure DB rejects it
        duplicate_raised = False
        try:
            cur.execute("""
                INSERT INTO predictions (complaint_id, version_number, predicted_window_start, predicted_window_end, window_label, created_at)
                VALUES (?, 1, '2026-09-01 12:00:00', '2026-09-01 14:00:00', 'Next 2–4 Hours', '2026-09-01 12:00:00')
            """, (c1_id,))
            conn.commit()
        except sqlite3.IntegrityError:
            duplicate_raised = True
        assert duplicate_raised, "Unique constraint on (complaint_id, version_number) failed to reject duplicate version!"

        conn.close()
    finally:
        try:
            if os.path.exists(temp_db_path):
                os.remove(temp_db_path)
        except Exception:
            pass


def test_upgrade_from_populated_0010_to_0011():
    """
    Test upgrading an existing database populated with Phase 2 data (up to 0010)
    to 0011 (canonical transaction deduplication):
    1. Schema upgrades to head smoothly.
    2. uq_transactions_transaction_ref is enforced as unique.
    3. Duplicate transaction_ref insertion is rejected by the database.
    """
    with tempfile.NamedTemporaryFile(suffix=".db", delete=False) as f:
        temp_db_path = f.name

    try:
        norm_path = temp_db_path.replace("\\", "/")

        # 1. Upgrade to 0010_explicit_analysis_purpose
        cmd_p1 = [
            sys.executable, "-m", "alembic",
            "-x", f"db_url=sqlite:///{norm_path}",
            "upgrade", "0010_explicit_analysis_purpose"
        ]
        res1 = subprocess.run(cmd_p1, capture_output=True, text=True)
        assert res1.returncode == 0, f"0010 upgrade failed: {res1.stderr}"

        # 2. Seed populated data into 0010 schema
        conn = sqlite3.connect(temp_db_path)
        cur = conn.cursor()

        cur.execute("""
            INSERT INTO accounts (account_number, masked_account, bank_name, holder_name, created_at)
            VALUES ('ACC-MIG-01', 'ACC••••0001', 'SBI', 'Test Holder 1', '2026-09-01 10:00:00')
        """)
        a1_id = cur.lastrowid

        cur.execute("""
            INSERT INTO accounts (account_number, masked_account, bank_name, holder_name, created_at)
            VALUES ('ACC-MIG-02', 'ACC••••0002', 'HDFC', 'Test Holder 2', '2026-09-01 10:00:00')
        """)
        a2_id = cur.lastrowid

        cur.execute("""
            INSERT INTO complaints (complaint_number, fraud_type, amount, victim_location, case_status, state, district, created_at)
            VALUES ('CMP-MIG-01', 'UPI_FRAUD', 50000.0, 'Rohini, Delhi', 'ACTIVE', 'Delhi', 'NORTH_WEST', '2026-09-01 10:00:00')
        """)
        c1_id = cur.lastrowid

        cur.execute("""
            INSERT INTO transactions (transaction_ref, complaint_id, sender_account_id, receiver_account_id, amount, timestamp, received_at)
            VALUES ('TX-MIG-001', ?, ?, ?, 50000.0, '2026-09-01 10:05:00', '2026-09-01 10:05:00')
        """, (c1_id, a1_id, a2_id))

        conn.commit()
        conn.close()

        # 3. Upgrade to 0011 (head)
        cmd_p2 = [
            sys.executable, "-m", "alembic",
            "-x", f"db_url=sqlite:///{norm_path}",
            "upgrade", "head"
        ]
        res2 = subprocess.run(cmd_p2, capture_output=True, text=True)
        assert res2.returncode == 0, f"0011 upgrade with populated data failed: {res2.stderr}"

        # 4. Verify canonical unique constraint / index on transactions.transaction_ref
        conn = sqlite3.connect(temp_db_path)
        cur = conn.cursor()

        cur.execute("PRAGMA index_list(transactions);")
        indexes = {row[1]: row[2] for row in cur.fetchall()}  # name: unique (1 or 0)

        # Verify index exists and is unique (either uq_transactions_transaction_ref or sqlite autoindex)
        has_unique_ref = False
        for idx_name, is_unique in indexes.items():
            if is_unique == 1:
                cur.execute(f"PRAGMA index_info({idx_name});")
                cols = [row[2] for row in cur.fetchall()]
                if "transaction_ref" in cols:
                    has_unique_ref = True
                    break
        assert has_unique_ref, f"Unique constraint/index on transaction_ref not found: {indexes}"

        # 5. Verify that database rejects duplicate transaction_ref insertion
        dup_raised = False
        try:
            cur.execute("""
                INSERT INTO transactions (transaction_ref, complaint_id, sender_account_id, receiver_account_id, amount, timestamp, received_at)
                VALUES ('TX-MIG-001', ?, ?, ?, 20000.0, '2026-09-01 10:10:00', '2026-09-01 10:10:00')
            """, (c1_id, a1_id, a2_id))
            conn.commit()
        except sqlite3.IntegrityError:
            dup_raised = True
        assert dup_raised, "Database failed to reject duplicate transaction_ref!"

        conn.close()
    finally:
        try:
            if os.path.exists(temp_db_path):
                os.remove(temp_db_path)
        except Exception:
            pass
