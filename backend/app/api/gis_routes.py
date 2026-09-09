from typing import List, Optional
from fastapi import APIRouter, Depends, HTTPException
from sqlalchemy.orm import Session
from backend.app.models.db import get_db
from backend.app.models.models import LocationCluster, ATMLocation, Complaint
from backend.app.schemas.schemas import HotspotCluster, ATMLocationItem, GISOverviewResponse

router = APIRouter(tags=["GIS & Risk Map"])

@router.get("/risk-map", response_model=GISOverviewResponse)
def get_risk_map_overview(
    district: Optional[str] = None,
    risk_level: Optional[str] = None,
    db: Session = Depends(get_db)
):
    query_clusters = db.query(LocationCluster)
    if district and district != "ALL":
        query_clusters = query_clusters.filter(LocationCluster.district.ilike(f"%{district}%"))

    clusters = query_clusters.all()

    hotspots = []
    for c in clusters:
        risk_lvl = "CRITICAL" if c.risk_score >= 0.80 else ("HIGH" if c.risk_score >= 0.60 else "MEDIUM")
        if risk_level and risk_level != "ALL" and risk_lvl != risk_level:
            continue

        # Expected window
        exp_win = "Next 2–4 Hours" if c.risk_score >= 0.80 else "Next 4–8 Hours"
        amt = 125000.0 if "Vijay" in c.cluster_name else (75000.0 if c.risk_score >= 0.70 else 35000.0)

        hotspots.append({
            "id": c.id,
            "cluster_name": c.cluster_name,
            "city": c.city,
            "district": c.district,
            "state": c.state,
            "latitude": c.center_lat,
            "longitude": c.center_lon,
            "radius_km": c.radius_km,
            "risk_score": c.risk_score,
            "risk_level": risk_lvl,
            "active_cases": 8 if "Vijay" in c.cluster_name else max(1, int(c.risk_score * 7)),
            "amount_at_risk": amt,
            "atm_count": c.atm_count or 6,
            "expected_window": exp_win,
            "fraud_type": "Investment / Mule Extraction"
        })

    atms_query = db.query(ATMLocation)
    if district and district != "ALL":
        atms_query = atms_query.filter(ATMLocation.district.ilike(f"%{district}%"))
    atms = atms_query.limit(100).all()

    atm_items = [
        {
            "id": a.id,
            "atm_code": a.atm_code,
            "bank_name": a.bank_name,
            "address": a.address,
            "city": a.city,
            "district": a.district,
            "latitude": a.latitude,
            "longitude": a.longitude,
            "cash_available": a.cash_available,
            "risk_rating": a.risk_rating,
            "cluster_name": a.cluster.cluster_name if a.cluster else "General Grid"
        }
        for a in atms
    ]

    summary = {
        "total_hotspots": len(hotspots),
        "critical_clusters": sum(1 for h in hotspots if h["risk_level"] == "CRITICAL"),
        "total_monitored_atms": len(atm_items),
        "primary_threat_epicenter": "Vijay Nagar, Indore",
        "state": "Madhya Pradesh"
    }

    return {
        "hotspots": hotspots,
        "atms": atm_items,
        "summary": summary
    }

@router.get("/clusters", response_model=List[HotspotCluster])
def list_clusters(db: Session = Depends(get_db)):
    clusters = db.query(LocationCluster).all()
    res = []
    for c in clusters:
        risk_lvl = "CRITICAL" if c.risk_score >= 0.80 else ("HIGH" if c.risk_score >= 0.60 else "MEDIUM")
        res.append({
            "id": c.id,
            "cluster_name": c.cluster_name,
            "city": c.city,
            "district": c.district,
            "state": c.state,
            "latitude": c.center_lat,
            "longitude": c.center_lon,
            "radius_km": c.radius_km,
            "risk_score": c.risk_score,
            "risk_level": risk_lvl,
            "active_cases": 6 if "Vijay" in c.cluster_name else 3,
            "amount_at_risk": 125000.0 if "Vijay" in c.cluster_name else 50000.0,
            "atm_count": c.atm_count or 5,
            "expected_window": "Next 2–4 Hours",
            "fraud_type": "Investment Scam / Mule Extraction"
        })
    return res

@router.get("/clusters/{id}", response_model=HotspotCluster)
def get_cluster(id: int, db: Session = Depends(get_db)):
    c = db.query(LocationCluster).filter(LocationCluster.id == id).first()
    if not c:
        raise HTTPException(status_code=404, detail="Cluster not found")

    risk_lvl = "CRITICAL" if c.risk_score >= 0.80 else ("HIGH" if c.risk_score >= 0.60 else "MEDIUM")
    return {
        "id": c.id,
        "cluster_name": c.cluster_name,
        "city": c.city,
        "district": c.district,
        "state": c.state,
        "latitude": c.center_lat,
        "longitude": c.center_lon,
        "radius_km": c.radius_km,
        "risk_score": c.risk_score,
        "risk_level": risk_lvl,
        "active_cases": 8 if "Vijay" in c.cluster_name else 4,
        "amount_at_risk": 125000.0,
        "atm_count": c.atm_count or 6,
        "expected_window": "Next 2–4 Hours",
        "fraud_type": "Investment Scam"
    }
