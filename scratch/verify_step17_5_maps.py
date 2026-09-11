import requests
import json
import psycopg

DB_URL = "postgresql://cybershield:cybershield_local_only@localhost:5432/cybershield"

def test_step17_5_integrity():
    print("=== STEP 17.5 MAP INTEGRITY & GIS AUDIT ===")
    
    # 1. Check Database Delhi clusters and Delhi ATMs
    conn = psycopg.connect(DB_URL)
    cur = conn.cursor()
    
    cur.execute("SELECT count(*) FROM location_clusters WHERE state = 'Delhi'")
    db_clusters_count = cur.fetchone()[0]
    print(f"Database Delhi Clusters count: {db_clusters_count} (Expected 60)")
    assert db_clusters_count == 60, f"Expected 60 Delhi clusters in DB, got {db_clusters_count}"
    
    cur.execute("""
        SELECT count(*) FROM atm_locations a
        JOIN location_clusters c ON a.cluster_id = c.id
        WHERE c.state = 'Delhi'
    """)
    db_atms_count = cur.fetchone()[0]
    print(f"Database Delhi Reference ATMs count: {db_atms_count} (Expected exactly 240)")
    assert db_atms_count == 240, f"Expected 240 Delhi ATMs in DB, got {db_atms_count}"
    
    # 2. Check GIS API response
    res = requests.get("http://127.0.0.1:8000/api/v1/risk-map")
    assert res.status_code == 200, f"GIS endpoint failed: {res.text}"
    gis_data = res.json()
    hotspots = gis_data.get("hotspots", [])
    atms = gis_data.get("atms", [])
    
    print(f"GIS API Hotspots count: {len(hotspots)} (Expected 60 Delhi clusters)")
    print(f"GIS API Reference ATMs returned: {len(atms)} (From 240 Delhi Reference dataset)")
    assert len(hotspots) == 60, f"Expected 60 Delhi clusters from API, got {len(hotspots)}"
    assert len(atms) > 0, "Expected ATM nodes to be returned"
    
    # Verify all returned ATMs have valid coordinates in Delhi corridor
    for atm in atms:
        assert atm["latitude"] is not None and atm["longitude"] is not None
        assert 28.0 <= atm["latitude"] <= 29.0, f"ATM outside Delhi: {atm}"
        assert 76.8 <= atm["longitude"] <= 77.6, f"ATM outside Delhi: {atm}"
    print(f"[PASS] All {len(atms)} returned ATMs verified within Delhi corridor coordinates.")
    
    # 3. Check Database counts before fetching prediction
    cur.execute("SELECT count(*) FROM predictions")
    preds_before = cur.fetchone()[0]
    cur.execute("SELECT count(*) FROM prediction_locations")
    locs_before = cur.fetchone()[0]
    cur.execute("SELECT count(*) FROM alerts")
    alerts_before = cur.fetchone()[0]
    
    # 4. Find a persisted Delhi complaint with prediction
    cur.execute("""
        SELECT c.complaint_number, p.id, p.primary_cluster_id
        FROM complaints c
        JOIN predictions p ON p.complaint_id = c.id
        ORDER BY p.id DESC LIMIT 1
    """)
    row = cur.fetchone()
    assert row is not None, "No persisted prediction found in DB"
    c_num, pred_id, primary_cluster_id = row
    print(f"Testing Complaint: {c_num} | DB Prediction ID: {pred_id}")
    
    # Fetch prediction as Case Intelligence does
    res_pred = requests.get(f"http://127.0.0.1:8000/api/v1/predictions/{c_num}")
    assert res_pred.status_code == 200
    pred_data = res_pred.json()
    case_intel_pred_id = pred_data["prediction_id"]
    top_locs = pred_data["top_locations"]
    
    print(f"Case Intelligence Prediction ID: {case_intel_pred_id}")
    print(f"Top-3 Locations count: {len(top_locs)}")
    assert len(top_locs) == 3, f"Expected 3 locations, got {len(top_locs)}"
    assert case_intel_pred_id == pred_id, f"ID mismatch: {case_intel_pred_id} vs {pred_id}"
    
    # Fetch again simulating Risk Map opening
    res_pred_map = requests.get(f"http://127.0.0.1:8000/api/v1/predictions/{c_num}")
    assert res_pred_map.status_code == 200
    risk_map_pred_id = res_pred_map.json()["prediction_id"]
    risk_map_locs = res_pred_map.json()["top_locations"]
    
    assert case_intel_pred_id == risk_map_pred_id, "Risk Map and Case Intelligence prediction IDs must match!"
    print(f"[PASS] Prediction ID consistency: Case Intel #{case_intel_pred_id} == Risk Map #{risk_map_pred_id}")
    
    for i in range(3):
        ci_loc = top_locs[i]
        rm_loc = risk_map_locs[i]
        assert ci_loc["rank"] == rm_loc["rank"] == i + 1
        assert ci_loc["location_name"] == rm_loc["location_name"]
        assert ci_loc["cluster_id"] == rm_loc["cluster_id"]
        assert ci_loc["latitude"] == rm_loc["latitude"]
        assert ci_loc["longitude"] == rm_loc["longitude"]
        print(f"  Rank #{i+1}: {ci_loc['location_name']} ({ci_loc['latitude']}, {ci_loc['longitude']}) Priority: {ci_loc['risk_level']}")
    
    # 5. Check Database counts after GET requests
    cur.execute("SELECT count(*) FROM predictions")
    preds_after = cur.fetchone()[0]
    cur.execute("SELECT count(*) FROM prediction_locations")
    locs_after = cur.fetchone()[0]
    cur.execute("SELECT count(*) FROM alerts")
    alerts_after = cur.fetchone()[0]
    
    print(f"Predictions created by map read: {preds_after - preds_before} (Expected: 0)")
    print(f"PredictionLocations created by map read: {locs_after - locs_before} (Expected: 0)")
    print(f"Alerts created by map read: {alerts_after - alerts_before} (Expected: 0)")
    
    assert preds_after == preds_before, "Map read must not create Prediction rows"
    assert locs_after == locs_before, "Map read must not create PredictionLocation rows"
    assert alerts_after == alerts_before, "Map read must not create Alert rows"
    
    cur.close()
    conn.close()
    print("=== STEP 17.5 BACKEND & PREDICTION INTEGRITY: 100% PASS ===")

if __name__ == "__main__":
    test_step17_5_integrity()
