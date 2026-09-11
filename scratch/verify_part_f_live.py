"""
CyberShield AI — Part F Live Complaint Verification Script
Registers 8 fresh Delhi complaints through the API across 8 diverse districts and collects live model outputs.
"""

import sys
sys.stdout.reconfigure(encoding='utf-8')
import json
from datetime import datetime, timedelta
from fastapi.testclient import TestClient
from backend.app.main import app
from backend.app.auth.security import create_access_token
from backend.app.models.db import SessionLocal
def format_inr(val):
    return f"₹{int(val):,}"

client = TestClient(app)

DELHI_LIVE_CASES = [
    {
        "name": "Case 1: Dwarka Sector 12 (South-West)",
        "victim_name": "Pooja Sharma",
        "fraud_type": "UPI / QR Code Fraud",
        "amount": 42000.0,
        "payment_channel": "UPI",
        "district": "South West Delhi",
        "locality": "Dwarka Sector 12",
        "victim_location": "Dwarka Sector 12, South West Delhi, Delhi",
        "victim_lat": 28.5921,
        "victim_lon": 77.0460,
        "victim_bank": "State Bank of India",
        "beneficiary_bank": "Paytm Payments Bank",
        "beneficiary_id": "mule.dwarka@paytm",
        "hours_ago": 1.5,
    },
    {
        "name": "Case 2: Rohini Sector 7 (North-West)",
        "victim_name": "Amit Bansal",
        "fraud_type": "Investment Scam",
        "amount": 250000.0,
        "payment_channel": "NEFT",
        "district": "North West Delhi",
        "locality": "Rohini Sector 7",
        "victim_location": "Rohini Sector 7, North West Delhi, Delhi",
        "victim_lat": 28.7159,
        "victim_lon": 77.1147,
        "victim_bank": "HDFC Bank",
        "beneficiary_bank": "ICICI Bank",
        "beneficiary_id": "mule.rohini@icici",
        "hours_ago": 2.0,
    },
    {
        "name": "Case 3: Saket District Centre (South)",
        "victim_name": "Rohan Malhotra",
        "fraud_type": "Digital Arrest / Impersonation",
        "amount": 180000.0,
        "payment_channel": "RTGS",
        "district": "South Delhi",
        "locality": "Saket",
        "victim_location": "Saket District Centre, South Delhi, Delhi",
        "victim_lat": 28.5244,
        "victim_lon": 77.2066,
        "victim_bank": "Axis Bank",
        "beneficiary_bank": "Kotak Mahindra Bank",
        "beneficiary_id": "mule.saket@kotak",
        "hours_ago": 0.8,
    },
    {
        "name": "Case 4: Laxmi Nagar Vikas Marg (East)",
        "victim_name": "Sunita Verma",
        "fraud_type": "Part-Time Job Fraud",
        "amount": 18500.0,
        "payment_channel": "UPI",
        "district": "East Delhi",
        "locality": "Laxmi Nagar",
        "victim_location": "Laxmi Nagar, East Delhi, Delhi",
        "victim_lat": 28.6279,
        "victim_lon": 77.2784,
        "victim_bank": "Punjab National Bank",
        "beneficiary_bank": "PhonePe / YES Bank",
        "beneficiary_id": "mule.laxmi@ybl",
        "hours_ago": 3.2,
    },
    {
        "name": "Case 5: Karol Bagh Arya Samaj Road (Central)",
        "victim_name": "Harpreet Singh",
        "fraud_type": "Loan App Extortion",
        "amount": 65000.0,
        "payment_channel": "IMPS",
        "district": "Central Delhi",
        "locality": "Karol Bagh",
        "victim_location": "Arya Samaj Road, Karol Bagh, Central Delhi, Delhi",
        "victim_lat": 28.6514,
        "victim_lon": 77.1907,
        "victim_bank": "Canara Bank",
        "beneficiary_bank": "Federal Bank",
        "beneficiary_id": "mule.karol@federal",
        "hours_ago": 1.2,
    },
    {
        "name": "Case 6: Janakpuri District Centre (West)",
        "victim_name": "Deepak Mehta",
        "fraud_type": "Credit Card / Phishing",
        "amount": 89000.0,
        "payment_channel": "Net Banking",
        "district": "West Delhi",
        "locality": "Janakpuri",
        "victim_location": "Janakpuri District Centre, West Delhi, Delhi",
        "victim_lat": 28.6219,
        "victim_lon": 77.0878,
        "victim_bank": "ICICI Bank",
        "beneficiary_bank": "IDFC First Bank",
        "beneficiary_id": "mule.janak@idfc",
        "hours_ago": 4.5,
    },
    {
        "name": "Case 7: Civil Lines Rajpur Road (North)",
        "victim_name": "Dr. K. S. Tyagi",
        "fraud_type": "Investment Scam",
        "amount": 550000.0,
        "payment_channel": "RTGS",
        "district": "North Delhi",
        "locality": "Civil Lines",
        "victim_location": "Rajpur Road, Civil Lines, North Delhi, Delhi",
        "victim_lat": 28.6814,
        "victim_lon": 77.2228,
        "victim_bank": "State Bank of India",
        "beneficiary_bank": "Standard Chartered",
        "beneficiary_id": "mule.civillines@scb",
        "hours_ago": 0.5,
    },
    {
        "name": "Case 8: Connaught Place Inner Circle (New Delhi)",
        "victim_name": "Ananya Roy",
        "fraud_type": "UPI / QR Code Fraud",
        "amount": 12000.0,
        "payment_channel": "UPI",
        "district": "New Delhi",
        "locality": "Connaught Place",
        "victim_location": "Connaught Place Inner Circle, New Delhi, Delhi",
        "victim_lat": 28.6315,
        "victim_lon": 77.2167,
        "victim_bank": "HDFC Bank",
        "beneficiary_bank": "Airtel Payments Bank",
        "beneficiary_id": "mule.cp@airtel",
        "hours_ago": 6.0,
    }
]

def run_live_verification():
    token = create_access_token({"sub": "admin@cybershield.gov.in", "role": "I4C_ADMIN"})
    headers = {"Authorization": f"Bearer {token}"}
    now = datetime.utcnow()

    results = []
    print("=" * 80)
    print("CYBERSHIELD AI — PART F LIVE REGISTRATION & PREDICTION AUDIT")
    print("=" * 80)

    for i, case in enumerate(DELHI_LIVE_CASES, 1):
        ts = int(now.timestamp()) + i
        ref = f"TXN-F{i}-{ts}"
        inc_time = now - timedelta(hours=case["hours_ago"])

        payload = {
            "victim_name": case["victim_name"],
            "fraud_type": case["fraud_type"],
            "amount": case["amount"],
            "incident_time": inc_time.isoformat(),
            "reported_at": now.isoformat(),
            "state": "Delhi",
            "district": case["district"],
            "locality": case["locality"],
            "victim_location": case["victim_location"],
            "victim_lat": case["victim_lat"],
            "victim_lon": case["victim_lon"],
            "payment_channel": case["payment_channel"],
            "victim_bank": case["victim_bank"],
            "beneficiary_bank": case["beneficiary_bank"],
            "beneficiary_id": case["beneficiary_id"],
            "transaction_ref": ref,
            "transaction_time": inc_time.isoformat(),
            "description": f"Live verification test intake for {case['name']}",
            "ifsc_code": "HDFC0000001",
            "beneficiary_account": f"50100998{i:04d}",
            "beneficiary_upi": case["beneficiary_id"]
        }

        resp = client.post("/api/v1/complaints", json=payload, headers=headers)
        assert resp.status_code in (200, 201), f"Complaint creation failed: {resp.text}"
        comp_data = resp.json()
        c_num = comp_data["complaint_number"]

        # Run prediction
        pred_resp = client.post(f"/api/v1/predictions/{c_num}", headers=headers)
        assert pred_resp.status_code == 200, f"Prediction failed: {pred_resp.text}"
        p_data = pred_resp.json()

        top_locs = p_data.get("top_locations", [])
        top1 = top_locs[0]["location_name"] if len(top_locs) > 0 else "N/A"
        top2 = top_locs[1]["location_name"] if len(top_locs) > 1 else "N/A"
        top3 = top_locs[2]["location_name"] if len(top_locs) > 2 else "N/A"

        time_pred = p_data.get("time_prediction", {})
        mins = time_pred.get("predicted_minutes_to_cashout", 0.0)
        window_str = p_data.get("when_window") or f"{int(mins)} mins"

        # Operational priority of top1
        priority = top_locs[0].get("risk_level", "N/A") if top_locs else "N/A"

        results.append({
            "complaint": c_num,
            "origin": case["locality"],
            "amount": format_inr(case["amount"]),
            "channel": case["payment_channel"],
            "fraud_type": case["fraud_type"],
            "top1": top1,
            "top2": top2,
            "top3": top3,
            "time": window_str,
            "time_mins": mins,
            "priority": priority,
            "top3_set": tuple(sorted([top1, top2, top3]))
        })

    # Summary table
    print(f"\n{'Complaint':<18} | {'Origin':<15} | {'Amount':<10} | {'Channel':<7} | {'Top 1 Location':<22} | {'Time Window':<18} | {'Priority'}")
    print("-" * 115)
    for r in results:
        print(f"{r['complaint']:<18} | {r['origin']:<15} | {r['amount']:<10} | {r['channel']:<7} | {r['top1']:<22} | {r['time']:<18} | {r['priority']}")

    unique_top1 = len(set(r["top1"] for r in results))
    unique_top3_sets = len(set(r["top3_set"] for r in results))
    min_time = min(r["time_mins"] for r in results)
    max_time = max(r["time_mins"] for r in results)
    priorities = {}
    for r in results:
        priorities[r["priority"]] = priorities.get(r["priority"], 0) + 1

    print("\nMETRICS SUMMARY:")
    print(f"Unique Top1 Locations: {unique_top1} / {len(results)}")
    print(f"Unique Top3 Sets:      {unique_top3_sets} / {len(results)}")
    print(f"Time Estimate Range:   {min_time:.1f} mins – {max_time:.1f} mins")
    print(f"Priority Distribution: {priorities}")
    print("=" * 80)

if __name__ == "__main__":
    run_live_verification()
