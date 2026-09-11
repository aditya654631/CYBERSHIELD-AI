"""
Phase 1 Step 6 Live Verification & Restart Stability Script
Tests live FastAPI server, endpoints, restart stability, and database deltas.
"""

import subprocess
import time
import urllib.request
import json
import os
import sys

from backend.app.models.db import SessionLocal
from backend.app.models.models import (
    Organization, User, LocationCluster, ATMLocation,
    Complaint, Account, ComplaintAccount, Transaction,
    Withdrawal, Prediction, PredictionLocation, Alert,
    CaseNote, AuditLog
)

def get_db_counts():
    db = SessionLocal()
    try:
        return {
            'organizations': db.query(Organization).count(),
            'users': db.query(User).count(),
            'location_clusters': db.query(LocationCluster).count(),
            'atm_locations': db.query(ATMLocation).count(),
            'complaints': db.query(Complaint).count(),
            'accounts': db.query(Account).count(),
            'complaint_accounts': db.query(ComplaintAccount).count(),
            'transactions': db.query(Transaction).count(),
            'withdrawals': db.query(Withdrawal).count(),
            'predictions': db.query(Prediction).count(),
            'prediction_locations': db.query(PredictionLocation).count(),
            'alerts': db.query(Alert).count(),
            'case_notes': db.query(CaseNote).count(),
            'audit_logs': db.query(AuditLog).count(),
        }
    finally:
        db.close()

def start_server():
    proc = subprocess.Popen(
        [sys.executable, "-m", "uvicorn", "backend.app.main:app", "--port", "8000", "--host", "127.0.0.1"],
        stdout=subprocess.PIPE,
        stderr=subprocess.PIPE
    )
    # Poll until ready
    for _ in range(30):
        try:
            with urllib.request.urlopen("http://127.0.0.1:8000/health", timeout=1) as resp:
                if resp.status == 200:
                    return proc
        except Exception:
            time.sleep(0.5)
    raise RuntimeError("Failed to start FastAPI server on port 8000")

def stop_server(proc):
    proc.terminate()
    try:
        proc.wait(timeout=5)
    except Exception:
        proc.kill()

def query_endpoint(path, token=None):
    url = f"http://127.0.0.1:8000{path}"
    headers = {}
    if token:
        headers["Authorization"] = f"Bearer {token}"
    req = urllib.request.Request(url, headers=headers)
    with urllib.request.urlopen(req, timeout=5) as resp:
        body = json.loads(resp.read().decode())
        resp_headers = dict(resp.headers)
        return resp.status, body, resp_headers

def login():
    data = json.dumps({"email": "admin@cybershield.gov.in", "password": "CyberAdmin@2026"}).encode("utf-8")
    req = urllib.request.Request("http://127.0.0.1:8000/api/v1/auth/login", data=data, headers={"Content-Type": "application/json"})
    with urllib.request.urlopen(req, timeout=5) as resp:
        return json.loads(resp.read().decode())["access_token"]

def main():
    print("=== 1. RECORDING DB COUNTS BEFORE RETRIEVAL ===")
    counts_before = get_db_counts()
    print("COUNTS BEFORE:", counts_before)

    print("\n=== 2. STARTING FASTAPI PROCESS 1 ===")
    p1 = start_server()
    print("Process 1 PID:", p1.pid)

    try:
        status, health, _ = query_endpoint("/health")
        print("GET /health:", status, health)
        token = login()

        # Query CMP-NEW-000002
        status_a, txs_a, headers_a = query_endpoint("/api/v1/complaints/CMP-NEW-000002/transactions", token)
        _, ctx_a, _ = query_endpoint("/api/v1/complaints/CMP-NEW-000002/transactions/context", token)
        ids_a = [t["id"] for t in txs_a]
        print(f"\n[CMP-NEW-000002]\n  HTTP: {status_a}\n  Context Type: {headers_a.get('X-Context-Type')}\n  Source Scenario: {headers_a.get('X-Source-Scenario')}\n  Tx Count: {len(txs_a)}\n  IDs: {ids_a}\n  Duplicates: {len(ids_a) - len(set(ids_a))}")

        # Query CMP-NEW-000003
        status_b, txs_b, headers_b = query_endpoint("/api/v1/complaints/CMP-NEW-000003/transactions", token)
        _, ctx_b, _ = query_endpoint("/api/v1/complaints/CMP-NEW-000003/transactions/context", token)
        ids_b = [t["id"] for t in txs_b]
        print(f"\n[CMP-NEW-000003]\n  HTTP: {status_b}\n  Context Type: {headers_b.get('X-Context-Type')}\n  Source Scenario: {headers_b.get('X-Source-Scenario')}\n  Tx Count: {len(txs_b)}\n  IDs: {ids_b}\n  Duplicates: {len(ids_b) - len(set(ids_b))}")

        # Query CMP-NEW-000004
        status_c, txs_c, headers_c = query_endpoint("/api/v1/complaints/CMP-NEW-000004/transactions", token)
        _, ctx_c, _ = query_endpoint("/api/v1/complaints/CMP-NEW-000004/transactions/context", token)
        ids_c = [t["id"] for t in txs_c]
        print(f"\n[CMP-NEW-000004]\n  HTTP: {status_c}\n  Context Type: {headers_c.get('X-Context-Type')}\n  Source Scenario: {headers_c.get('X-Source-Scenario')}\n  Tx Count: {len(txs_c)}\n  IDs: {ids_c}\n  Duplicates: {len(ids_c) - len(set(ids_c))}")

        # Query CMP-1042
        status_demo, txs_demo, headers_demo = query_endpoint("/api/v1/complaints/CMP-1042/transactions", token)
        ids_demo = [t["id"] for t in txs_demo]
        print(f"\n[CMP-1042]\n  HTTP: {status_demo}\n  Context Type: {headers_demo.get('X-Context-Type')}\n  Source Scenario: {headers_demo.get('X-Source-Scenario')}\n  Tx Count: {len(txs_demo)}\n  IDs: {ids_demo}\n  Duplicates: {len(ids_demo) - len(set(ids_demo))}")

        # Query CMP-DL-0001
        status_dl, txs_dl, headers_dl = query_endpoint("/api/v1/complaints/CMP-DL-0001/transactions", token)
        ids_dl = [t["id"] for t in txs_dl]
        print(f"\n[CMP-DL-0001]\n  HTTP: {status_dl}\n  Context Type: {headers_dl.get('X-Context-Type')}\n  Source Scenario: {headers_dl.get('X-Source-Scenario')}\n  Tx Count: {len(txs_dl)}\n  IDs: {ids_dl}\n  Duplicates: {len(ids_dl) - len(set(ids_dl))}")

    finally:
        print("\n=== 3. STOPPING PROCESS 1 ===")
        stop_server(p1)

    print("\n=== 4. STARTING FRESH FASTAPI PROCESS 2 (RESTART TEST) ===")
    p2 = start_server()
    print("Process 2 PID:", p2.pid)

    try:
        token2 = login()
        # Re-query CMP-NEW-000002
        _, txs_a_restart, headers_a_restart = query_endpoint("/api/v1/complaints/CMP-NEW-000002/transactions", token2)
        ids_a_restart = [t["id"] for t in txs_a_restart]

        # Re-query CMP-NEW-000003
        _, txs_b_restart, headers_b_restart = query_endpoint("/api/v1/complaints/CMP-NEW-000003/transactions", token2)
        ids_b_restart = [t["id"] for t in txs_b_restart]

        print("\n=== RESTART COMPARISON ===")
        print("CMP-NEW-000002 Source Before vs After:", headers_a.get('X-Source-Scenario'), "vs", headers_a_restart.get('X-Source-Scenario'), "-> MATCH?", headers_a.get('X-Source-Scenario') == headers_a_restart.get('X-Source-Scenario'))
        print("CMP-NEW-000002 Count Before vs After:", len(txs_a), "vs", len(txs_a_restart), "-> MATCH?", len(txs_a) == len(txs_a_restart))
        print("CMP-NEW-000002 IDs & Order Before vs After:", ids_a, "vs", ids_a_restart, "-> IDENTICAL?", ids_a == ids_a_restart)

        print("CMP-NEW-000003 Source Before vs After:", headers_b.get('X-Source-Scenario'), "vs", headers_b_restart.get('X-Source-Scenario'), "-> MATCH?", headers_b.get('X-Source-Scenario') == headers_b_restart.get('X-Source-Scenario'))
        print("CMP-NEW-000003 Count Before vs After:", len(txs_b), "vs", len(txs_b_restart), "-> MATCH?", len(txs_b) == len(txs_b_restart))
        print("CMP-NEW-000003 IDs & Order Before vs After:", ids_b, "vs", ids_b_restart, "-> IDENTICAL?", ids_b == ids_b_restart)

        assert ids_a == ids_a_restart, "CMP-NEW-000002 transaction IDs or ordering changed across restart!"
        assert ids_b == ids_b_restart, "CMP-NEW-000003 transaction IDs or ordering changed across restart!"

    finally:
        print("\n=== 5. STOPPING PROCESS 2 ===")
        stop_server(p2)

    print("\n=== 6. RECORDING DB COUNTS AFTER RETRIEVAL ===")
    counts_after = get_db_counts()
    print("COUNTS AFTER:", counts_after)

    deltas = {k: counts_after[k] - counts_before[k] for k in counts_before}
    print("TABLE DELTAS:", deltas)

if __name__ == "__main__":
    main()
