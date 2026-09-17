from typing import List, Optional, Dict, Any
from datetime import datetime, timezone, timedelta
from collections import Counter
from fastapi import APIRouter, Depends, HTTPException, status
from sqlalchemy import func
from sqlalchemy.orm import Session, joinedload
from backend.app.models.db import get_db
from backend.app.models.models import LocationCluster, ATMLocation, Complaint, Prediction, PredictionLocation, User
from backend.app.schemas.schemas import HotspotCluster, ATMLocationItem, GISOverviewResponse
from backend.app.auth.security import get_current_user
from backend.app.auth.rbac import verify_complaint_access, filter_complaints_by_jurisdiction, RoleEnum

router = APIRouter(tags=["GIS & Risk Map"])

PRIORITY_ORDER = {"CRITICAL": 4, "HIGH": 3, "MEDIUM": 2, "LOW": 1}


def format_window_ist(start_dt: Optional[datetime], end_dt: Optional[datetime]) -> str:
    """Format window bounds in Indian Standard Time (UTC+05:30) with explicit IST label."""
    if not start_dt or not end_dt:
        return "No active case prediction"
    ist_tz = timezone(timedelta(hours=5, minutes=30))
    start_ist = start_dt.replace(tzinfo=timezone.utc).astimezone(ist_tz)
    end_ist = end_dt.replace(tzinfo=timezone.utc).astimezone(ist_tz)

    start_date = start_ist.strftime("%d %b %Y")
    end_date = end_ist.strftime("%d %b %Y")
    start_time = start_ist.strftime("%H:%M")
    end_time = end_ist.strftime("%H:%M")

    if start_date == end_date:
        return f"{start_date}, {start_time} – {end_time} IST"
    return f"{start_date}, {start_time} IST – {end_date}, {end_time} IST"


def _cluster_items(
    db: Session,
    clusters: List[LocationCluster],
    allowed_state: Optional[str] = None,
    user: Optional[User] = None
) -> tuple:
    """
    Catalog geography plus current persisted case evidence, with no dummy KPIs.
    Returns (items: List[dict], evidence: Dict[int, dict])
    where evidence maps cluster_id -> dict of complaint_id -> {'prediction': pred, 'complaint': comp, 'locations': [loc, ...]}.
    """
    if not clusters:
        return [], {}
    cluster_ids = [cluster.id for cluster in clusters]
    atm_counts = dict(db.query(ATMLocation.cluster_id, func.count(ATMLocation.id)).filter(
        ATMLocation.cluster_id.in_(cluster_ids)
    ).group_by(ATMLocation.cluster_id).all())

    # Deterministically identify the latest prediction per complaint
    # using canonical ordering: created_at DESC, id DESC with row_number() = 1
    latest_subq = (
        db.query(
            Prediction.id.label("pred_id"),
            func.row_number().over(
                partition_by=Prediction.complaint_id,
                order_by=(Prediction.created_at.desc(), Prediction.id.desc())
            ).label("rn")
        ).subquery()
    )

    now_utc = datetime.utcnow()
    comp_filter = [
        PredictionLocation.cluster_id.in_(cluster_ids),
        ~func.upper(Complaint.case_status).in_(["RESOLVED", "CLOSED"]),
        Prediction.predicted_window_start.isnot(None),
        Prediction.predicted_window_end.isnot(None),
        Prediction.predicted_window_end > Prediction.predicted_window_start,
        Prediction.predicted_window_end > now_utc,
    ]

    rows_query = db.query(PredictionLocation, Prediction, Complaint).join(
        Prediction, PredictionLocation.prediction_id == Prediction.id
    ).join(
        latest_subq, Prediction.id == latest_subq.c.pred_id
    ).filter(
        latest_subq.c.rn == 1
    ).join(
        Complaint, Prediction.complaint_id == Complaint.id
    ).filter(*comp_filter)

    if user:
        rows_query = filter_complaints_by_jurisdiction(rows_query, user, db)
    elif allowed_state:
        rows_query = rows_query.filter(func.lower(Complaint.state) == allowed_state.lower())

    rows = rows_query.all()

    evidence: Dict[int, Dict[int, Any]] = {}
    for location, prediction, complaint in rows:
        cluster_entry = evidence.setdefault(location.cluster_id, {})
        if complaint.id not in cluster_entry:
            cluster_entry[complaint.id] = {
                "prediction": prediction,
                "complaint": complaint,
                "locations": []
            }
        cluster_entry[complaint.id]["locations"].append(location)

    result = []
    for cluster in clusters:
        cases = list(evidence.get(cluster.id, {}).values())
        active_cases = len(cases)
        historical_risk = float(cluster.risk_score or 0.0)

        if active_cases > 0:
            is_active = True
            data_basis = "active_prediction"
            # Candidate score: maximum candidate probability among locations in this cluster
            candidate_probs = [
                float(loc.probability)
                for item in cases
                for loc in item["locations"]
                if loc.probability is not None
            ]
            candidate_score = max(candidate_probs) if candidate_probs else 0.0

            # Operational priority: highest priority among candidate locations in this cluster
            priorities = [
                (loc.risk_level or "LOW").upper()
                for item in cases
                for loc in item["locations"]
            ]
            operational_priority = max(priorities, key=lambda p: PRIORITY_ORDER.get(p, 0)) if priorities else "LOW"
            operational_priority_basis = (
                f"Candidate score {candidate_score * 100:.1f}%; operational priority {operational_priority} "
                f"across {active_cases} linked case(s)"
            )

            # Deduplicate complaints within this cluster: sum unique complaint amounts
            associated_amount = sum(float(item["complaint"].amount or 0.0) for item in cases)

            # Earliest and latest expiring active predictions for operational window
            earliest_pred = min((item["prediction"] for item in cases), key=lambda p: p.predicted_window_end)
            latest_pred = max((item["prediction"] for item in cases), key=lambda p: p.predicted_window_end)
            w_start_iso = earliest_pred.predicted_window_start.replace(tzinfo=timezone.utc).isoformat()
            w_end_iso = earliest_pred.predicted_window_end.replace(tzinfo=timezone.utc).isoformat()
            latest_end_iso = latest_pred.predicted_window_end.replace(tzinfo=timezone.utc).isoformat()
            w_status = "active"
            expected_window = format_window_ist(earliest_pred.predicted_window_start, earliest_pred.predicted_window_end)

            linked_numbers = sorted(list({item["complaint"].complaint_number for item in cases if item["complaint"].complaint_number}))
            fraud_counts = Counter(item["complaint"].fraud_type for item in cases if item["complaint"].fraud_type)
            fraud_type_str = ", ".join(fraud for fraud, _ in fraud_counts.most_common(3)) or "Active Fraud Case"

            # Legacy compatibility fields
            risk_score = candidate_score
            risk_level = operational_priority
            amount_at_risk = associated_amount
        else:
            is_active = False
            data_basis = "historical_baseline"
            candidate_score = None
            operational_priority = None
            operational_priority_basis = "No active case prediction in current operational window"
            associated_amount = 0.0
            w_start_iso = None
            w_end_iso = None
            latest_end_iso = None
            w_status = "none"
            expected_window = "No active case prediction"
            linked_numbers = []
            fraud_type_str = "Historical baseline"

            # Historical risk must NEVER be substituted into active model score!
            risk_score = 0.0
            risk_level = "LOW"
            amount_at_risk = 0.0

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
            "active_cases": active_cases,
            "amount_at_risk": amount_at_risk,
            "atm_count": atm_counts.get(cluster.id, 0),
            "expected_window": expected_window,
            "fraud_type": fraud_type_str,

            # Additive fields
            "is_active_candidate": is_active,
            "data_basis": data_basis,
            "historical_risk": historical_risk,
            "candidate_score": candidate_score,
            "operational_priority": operational_priority,
            "operational_priority_basis": operational_priority_basis,
            "associated_complaint_amount": associated_amount,
            "window_start": w_start_iso,
            "window_end": w_end_iso,
            "latest_window_end": latest_end_iso,
            "window_status": w_status,
            "linked_complaint_numbers": linked_numbers,
        })

    # Sort active candidates first (by active_cases desc, priority desc, candidate_score desc),
    # then historical hotspots by historical_risk desc
    sorted_items = sorted(
        result,
        key=lambda row: (
            0 if row["is_active_candidate"] else 1,
            -row["active_cases"],
            -PRIORITY_ORDER.get(row["operational_priority"] or "", 0),
            -(row["candidate_score"] or 0.0),
            -(row["historical_risk"] or 0.0),
            row["id"]
        )
    )
    return sorted_items, evidence


@router.get("/risk-map", response_model=GISOverviewResponse)
def get_risk_map_overview(
    district: Optional[str] = None,
    risk_level: Optional[str] = None,
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user)
):
    user_role = getattr(current_user, "role", None) if isinstance(current_user, User) else None
    query_clusters = db.query(LocationCluster)

    # Jurisdiction filter
    target_state = "Delhi"
    if user_role == RoleEnum.STATE_LEA:
        target_state = current_user.organization.state if current_user.organization else "Delhi"
        query_clusters = query_clusters.filter(func.lower(LocationCluster.state) == target_state.lower())
    elif user_role == RoleEnum.DISTRICT_LEA:
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

    effective_user = current_user if isinstance(current_user, User) else None
    hotspots, evidence = _cluster_items(db, clusters, allowed_state=target_state, user=effective_user)
    if risk_level and risk_level != "ALL":
        hotspots = [item for item in hotspots if item["risk_level"] == risk_level.upper() or item.get("operational_priority") == risk_level.upper()]

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

    active_candidates = [h for h in hotspots if h["is_active_candidate"]]
    historical_hotspots = [h for h in hotspots if not h["is_active_candidate"]]

    # Global unique deduplication of complaints across all candidate clusters
    # A single complaint might appear in multiple candidate zones (Rank 1, Rank 2)
    # Global exposure must count that complaint's amount ONCE, not sum overlapping zones!
    unique_active_complaints: Dict[int, float] = {}
    for cluster_entry in evidence.values():
        for comp_id, item in cluster_entry.items():
            if comp_id not in unique_active_complaints:
                unique_active_complaints[comp_id] = float(item["complaint"].amount or 0.0)

    total_associated_amount = sum(unique_active_complaints.values())
    total_unique_active_cases = len(unique_active_complaints)

    summary = {
        "total_hotspots": len(hotspots),
        "total_active_candidates": len(active_candidates),
        "total_historical_hotspots": len(historical_hotspots),
        "critical_clusters": sum(1 for h in active_candidates if h.get("operational_priority") == "CRITICAL"),
        "total_associated_amount": total_associated_amount,
        "total_unique_active_cases": total_unique_active_cases,
        "total_monitored_atms": len(atm_items),
        "primary_threat_epicenter": active_candidates[0]["cluster_name"] if active_candidates else "No active case prediction",
        "state": target_state,
        "data_basis": f"{target_state} catalog; active interception candidates reflect latest unexpired predictions with global complaint deduplication.",
    }

    return {
        "hotspots": hotspots,
        "active_candidates": active_candidates,
        "historical_hotspots": historical_hotspots,
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
    items, _ = _cluster_items(db, clusters, allowed_state=target_state, user=current_user)
    return items


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

    items, _ = _cluster_items(db, [c], allowed_state=c.state, user=current_user)
    return items[0]


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
