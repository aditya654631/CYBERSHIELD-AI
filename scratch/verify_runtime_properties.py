"""
Verification for Section 18 (Live Runtime Verification) and Section 19 (Determinism).
"""
import sys
sys.stdout.reconfigure(encoding="utf-8")
from backend.app.models.db import SessionLocal
from backend.app.models.models import Complaint
from backend.app.services.prediction_service import MLPredictionProvider, PredictionService

def verify_runtime():
    db = SessionLocal()
    try:
        provider = MLPredictionProvider()
        service = PredictionService()

        print(f"Location model_version: {provider.model_version}")
        print(f"Time model_version:     {provider.time_model_version}")
        print(f"Location features used: {len(provider.feature_schema.get('location_features', [])) if provider.feature_schema else 43}")
        print(f"Time features used:     {len(provider.feature_schema.get('time_features', [])) if provider.feature_schema else 20}")
        print(f"Candidate pool size:    {provider.candidate_pool_size}")

        # Choose already registered Delhi complaint
        comp = db.query(Complaint).filter(Complaint.complaint_number == "CMP-DL-0001").first()
        if not comp:
            comp = db.query(Complaint).filter(Complaint.state == "Delhi").first()

        print(f"Auditing complaint: {comp.complaint_number}")

        # Inspect prediction
        res1 = provider.predict(comp, db)
        res2 = provider.predict(comp, db)

        loc1 = [(l["rank"], l["cluster_id"], l["location_name"]) for l in res1["top_locations"]]
        loc2 = [(l["rank"], l["cluster_id"], l["location_name"]) for l in res2["top_locations"]]
        time1 = res1["time_prediction"]["predicted_minutes_to_cashout"]
        time2 = res2["time_prediction"]["predicted_minutes_to_cashout"]

        print(f"Prediction 1 Top1: {loc1[0]} | Time: {time1:.2f} mins")
        print(f"Prediction 2 Top1: {loc2[0]} | Time: {time2:.2f} mins")
        print(f"Deterministic Location: {loc1 == loc2}")
        print(f"Deterministic Time:     {time1 == time2}")

    finally:
        db.close()

if __name__ == "__main__":
    verify_runtime()
