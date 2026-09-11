import os
import sys
import requests

BASE_URL = "http://127.0.0.1:8000"

def run_smoke_checks():
    print("==================================================")
    print("CYBERSHIELD AI — STEP 17 DATABASE SMOKE CHECKS")
    print("==================================================")

    # 1. /health
    r_health = requests.get(f"{BASE_URL}/health", timeout=5)
    print(f"1. /health Status: {r_health.status_code}")
    assert r_health.status_code == 200, f"/health failed: {r_health.text}"
    health_data = r_health.json()
    print(f"   Database Status: {health_data['database']['status']}, Engine: {health_data['database']['engine']}")
    assert health_data["status"] == "healthy"
    assert health_data["database"]["status"] == "connected"

    # 2. Authenticated Login
    r_login = requests.post(f"{BASE_URL}/api/v1/auth/login", json={
        "email": "admin@cybershield.gov.in",
        "password": "CyberAdmin@2026"
    }, timeout=5)
    print(f"2. /auth/login Status: {r_login.status_code}")
    assert r_login.status_code == 200, f"Login failed: {r_login.text}"
    token = r_login.json()["access_token"]
    headers = {"Authorization": f"Bearer {token}"}

    # 3. Complaints GET
    r_comp = requests.get(f"{BASE_URL}/api/v1/complaints?limit=5", headers=headers, timeout=5)
    print(f"3. /complaints Status: {r_comp.status_code}")
    assert r_comp.status_code == 200, f"Complaints GET failed: {r_comp.text}"
    complaints = r_comp.json()
    print(f"   Retrieved {len(complaints)} complaints from DB (Total header: {r_comp.headers.get('X-Total-Count')})")

    # 4. Dashboard Summary GET
    r_dash = requests.get(f"{BASE_URL}/api/v1/dashboard/summary", headers=headers, timeout=5)
    print(f"4. /dashboard/summary Status: {r_dash.status_code}")
    assert r_dash.status_code == 200, f"Dashboard summary failed: {r_dash.text}"
    dash_data = r_dash.json()
    print(f"   Dashboard KPIs: Active Complaints={dash_data['kpis']['active_complaints']}, Alerts={dash_data['kpis']['active_alerts']}")

    # 5. Location Cluster Retrieval (GIS)
    r_clusters = requests.get(f"{BASE_URL}/api/v1/clusters", headers=headers, timeout=5)
    print(f"5. /clusters Status: {r_clusters.status_code}")
    assert r_clusters.status_code == 200, f"Clusters GET failed: {r_clusters.text}"
    clusters = r_clusters.json()
    print(f"   Retrieved {len(clusters)} location clusters (Delhi Pilot)")
    assert len(clusters) >= 60

    print("\nALL SMOKE CHECKS PASSED: ZERO SCHEMA ERRORS.")

if __name__ == "__main__":
    run_smoke_checks()
