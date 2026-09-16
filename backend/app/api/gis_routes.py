from typing import List, Optional
from datetime import datetime, timezone
from collections import Counter
from fastapi import APIRouter, Depends, HTTPException, status
from sqlalchemy import func
from sqlalchemy.orm import Session, joinedload
from backend.app.models.db import get_db
from backend.app.models.models import LocationCluster, ATMLocation, Complaint, Prediction, PredictionLocation, User
from backend.app.schemas.schemas import HotspotCluster, ATMLocationItem, GISOverviewResponse
from backend.app.auth.security import get_current_user
from backend.app.auth.rbac import verify_complaint_access, RoleEnum

router = APIRouter(tags=["GIS & Risk Map"])


def _cluster_items(db: Session, clusters: List[LocationCluster], allowed_state: Optional[str] = None) -> List[dict]:
    """Catalog geography plus current persisted case evidence, with no dummy KPIs."""
    if not clusters:
        return []
    cluster_ids = [cluster.id for cluster in clusters]
    atm_counts = dict(db.query(ATMLocation.cluster_id, func.count(ATMLocation.id)).filter(
        ATMLocation.cluster_id.in_(cluster_ids)
    ).group_by(ATMLocation.cluster_id).all())
    latest = db.query(func.max(Prediction.id).label("id")).group_by(Prediction.complaint_id).subquery()
    comp_filter = [
        PredictionLocation.cluster_id.in_(cluster_ids),
        ~func.upper(Complaint.case_status).in_(["RESOLVED", "CLOSED"]),
        Prediction.predicted_window_end > datetime.utcnow(),
    ]
    if allowed_state:
        comp_filter.append(func.lower(Complaint.state) == allowed_state.lower())

    rows = db.query(PredictionLocation, Prediction, Complaint).join(
        Prediction, PredictionLocation.prediction_id == Prediction.id
    ).join(latest, Prediction.id == latest.c.id).join(
        Complaint, Prediction.complaint_id == Complaint.id
    ).filter(*comp_filter).all()

    evidence = {}
    for location, prediction, complaint in rows:
        evidence.setdefault(location.cluster_id, {})[complaint.id] = (prediction, complaint)

    result = []
    for cluster in clusters:
        cases = list(evidence.get(cluster.id, {}).values())
        risk_score = max((float(pred.risk_score or 0) for pred, _ in cases), default=float(cluster.risk_score or 0))
        risk_level = "CRITICAL" if risk_score >= .8 else "HIGH" if risk_score >= .6 else "MEDIUM" if risk_score >= .4 else "LOW"
        earliest = min((pred for pred, _ in cases), key=lambda pred: pred.predicted_window_end, default=None)
        window = "No active case prediction"
        if earliest:
            start = earliest.predicted_window_start.replace(tzinfo=timezone.utc).isoformat()
            end = earliest.predicted_window_end.replace(tzinfo=timezone.utc).isoformat()
            window = f"{start} – {end}"
        fraud_counts = Counter(comp.fraud_type for _, comp in cases)
        result.append({
            "id": cluster.id,
            "cluster_name": cluster.cluster_name,
            "city": cluster.city,
            "district": cluster.district,
            "state": cluster.state,
            "latitude": cluster.center_lat,
            "longitude": cluster.center_lon,
            "radius_km": cluster.radius_km,
            "risk_score": risk_score,
            "risk_level": risk_level,
            "active_cases": len(cases),
            "amount_at_risk": sum(float(comp.amount) for _, comp in cases),
            "atm_count": atm_counts.get(cluster.id, 0),
            "expected_window": window,
            "fraud_type": ", ".join(fraud for fraud, _ in fraud_counts.most_common(3)) or "No active case prediction",
        })
    return sorted(result, key=lambda row: (-row["active_cases"], -row["risk_score"], row["id"]))


@router.get("/risk-map", response_model=GISOverviewResponse)
def get_risk_map_overview(
    district: Optional[str] = None,
    risk_level: Optional[str] = None,
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user)
):
    query_clusters = db.query(LocationCluster)

    # Jurisdiction filter
    target_state = "Delhi"
    if current_user.role == RoleEnum.STATE_LEA:
        target_state = current_user.organization.state if current_user.organization else "Delhi"
        query_clusters = query_clusters.filter(func.lower(LocationCluster.state) == target_state.lower())
    elif current_user.role == RoleEnum.DISTRICT_LEA:
        target_state = current_user.organization.state if current_user.organization else "Delhi"
        target_district = current_user.organization.district if current_user.organization else "Central"
        query_clusters = query_clusters.filter(
            func.lower(LocationCluster.state) == target_state.lower(),
            func.lower(LocationCluster.district) == target_district.lower()
        )
    else:
        if district and district != "ALL":
            query_clusters = query_clusters.filter(LocationCluster.district.ilike(f"%{district}%"))
        else:
            query_clusters = query_clusters.filter(LocationCluster.state == "Delhi")

    clusters = query_clusters.order_by(LocationCluster.risk_score.desc()).all()

    hotspots = _cluster_items(db, clusters, allowed_state=target_state)
    if risk_level and risk_level != "ALL":
        hotspots = [item for item in hotspots if item["risk_level"] == risk_level.upper()]
    visible_cluster_ids = [item["id"] for item in hotspots]
    atms = db.query(ATMLocation).options(joinedload(ATMLocation.cluster)).filter(
        ATMLocation.cluster_id.in_(visible_cluster_ids)
    ).order_by(ATMLocation.id).all()

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
        "primary_threat_epicenter": hotspots[0]["cluster_name"] if hotspots and hotspots[0]["active_cases"] else "No active case prediction",
        "state": target_state,
        "data_basis": f"{target_state} catalog; active cases use the latest persisted, unexpired prediction per complaint.",
    }

    return {
        "hotspots": hotspots,
        "atms": atm_items,
        "summary": summary
    }


@router.get("/clusters", response_model=List[HotspotCluster])
def list_clusters(
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user)
):
    query = db.query(LocationCluster)
    target_state = "Delhi"
    if current_user.role == RoleEnum.STATE_LEA:
        target_state = current_user.organization.state if current_user.organization else "Delhi"
        query = query.filter(func.lower(LocationCluster.state) == target_state.lower())
    elif current_user.role == RoleEnum.DISTRICT_LEA:
        target_state = current_user.organization.state if current_user.organization else "Delhi"
        target_district = current_user.organization.district if current_user.organization else "Central"
        query = query.filter(
            func.lower(LocationCluster.state) == target_state.lower(),
            func.lower(LocationCluster.district) == target_district.lower()
        )
    else:
        query = query.filter(LocationCluster.state == "Delhi")

    clusters = query.order_by(LocationCluster.risk_score.desc()).all()
    return _cluster_items(db, clusters, allowed_state=target_state)


@router.get("/clusters/{id}", response_model=HotspotCluster)
def get_cluster(
    id: int,
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user)
):
    c = db.query(LocationCluster).filter(LocationCluster.id == id).first()
    if not c:
        raise HTTPException(status_code=404, detail="Cluster not found")

    # Jurisdiction check
    if current_user.role == RoleEnum.STATE_LEA:
        state = current_user.organization.state if current_user.organization else "Delhi"
        if (c.state or "").lower() != state.lower():
            raise HTTPException(status_code=404, detail="Cluster not found")
    elif current_user.role == RoleEnum.DISTRICT_LEA:
        state = current_user.organization.state if current_user.organization else "Delhi"
        district = current_user.organization.district if current_user.organization else "Central"
        if (c.state or "").lower() != state.lower() or (c.district or "").lower() != district.lower():
            raise HTTPException(status_code=404, detail="Cluster not found")

    return _cluster_items(db, [c], allowed_state=c.state)[0]


@router.get("/risk-map/prediction/{complaint_id}")
def get_gis_prediction_overlay(
    complaint_id: str,
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user)
):
    """
    GIS prediction overlay retrieval:
    Reads persisted Prediction and PredictionLocation rows directly.
    Requires JWT and verifies object-level jurisdiction.
    """
    if complaint_id.isdigit():
        complaint = db.query(Complaint).filter(Complaint.id == int(complaint_id)).first()
    else:
        complaint = db.query(Complaint).filter(Complaint.complaint_number == complaint_id).first()

    if not complaint or not verify_complaint_access(complaint, current_user, db):
        raise HTTPException(status_code=404, detail="Complaint not found")

    from backend.app.services.prediction_persistence_service import prediction_persistence_service
    from backend.app.api.prediction_routes import _format_prediction_response

    latest_pred = prediction_persistence_service.get_latest_prediction(db, complaint.id)
    if not latest_pred:
        raise HTTPException(
            status_code=404,
            detail=f"No persisted prediction found for complaint {complaint.complaint_number}."
        )

    return _format_prediction_response(latest_pred, complaint)
