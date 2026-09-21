from typing import List, Optional, Dict, Any
from datetime import datetime, timezone, timedelta
from collections import Counter
from fastapi import APIRouter, Depends, HTTPException, status
from sqlalchemy import func
from sqlalchemy.orm import Session, joinedload
from backend.app.models.db import get_db
from backend.app.models.models import LocationCluster, ATMLocation, Complaint, Prediction, PredictionLocation, User
from backend.app.schemas.schemas import HotspotCluster, ATMLocationItem, GISOverviewResponse, PredictionResponse
from backend.app.auth.security import get_current_user
from backend.app.auth.rbac import (
    verify_complaint_access, filter_complaints_by_jurisdiction,
    is_national_scope, RoleEnum,
)

router = APIRouter(tags=["GIS & Risk Map"])

PRIORITY_ORDER = {"CRITICAL": 4, "HIGH": 3, "MEDIUM": 2, "LOW": 1}


def _scope_cluster_query(query, db: Session, user: User):
    """Apply the same trusted scope to GIS collection and direct cluster reads."""
    if is_national_scope(user):
        return query
    if user.role in (RoleEnum.STATE_LEA, RoleEnum.DISTRICT_LEA, RoleEnum.ANALYST, RoleEnum.AUDITOR):
        org = user.organization
        if not org or not org.state:
            return query.filter(LocationCluster.id == -1)
        query = query.filter(func.lower(LocationCluster.state) == org.state.strip().lower())
        if user.role == RoleEnum.DISTRICT_LEA or (
            user.role in (RoleEnum.ANALYST, RoleEnum.AUDITOR)
            and org.district and org.district.upper() not in ("ALL", "NATIONAL")
        ):
            query = query.filter(func.lower(LocationCluster.district) == (org.district or "").strip().lower())
        return query
    if user.role == RoleEnum.BANK_OFFICER:
        visible_complaints = filter_complaints_by_jurisdiction(db.query(Complaint.id), user, db)
        visible_clusters = (
            db.query(PredictionLocation.cluster_id)
            .join(Prediction, PredictionLocation.prediction_id == Prediction.id)
            .filter(Prediction.complaint_id.in_(visible_complaints))
        )
        return query.filter(LocationCluster.id.in_(visible_clusters))
    return query.filter(LocationCluster.id == -1)


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


def _parse_iso_timestamp(ts_str: Optional[str], param_name: str) -> Optional[datetime]:
    """Parse ISO 8601 string and normalize to naive UTC datetime."""
    if not ts_str or not ts_str.strip():
        return None
    val = ts_str.strip()
    try:
        if val.endswith("Z") or val.endswith("z"):
            dt = datetime.fromisoformat(val[:-1] + "+00:00")
        else:
            dt = datetime.fromisoformat(val)
        if dt.tzinfo is not None:
            return dt.astimezone(timezone.utc).replace(tzinfo=None)
        return dt
    except Exception:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail=f"Invalid ISO datetime format for '{param_name}': '{ts_str}'. Expected valid ISO 8601 string."
        )


def _validate_time_filter(
    start_time: Optional[str],
    end_time: Optional[str],
    time_basis: Optional[str]
) -> tuple:
    """Validate time basis and range bounds."""
    basis = (time_basis or "predicted_window").strip().lower()
    valid_bases = {"predicted_window", "complaint_time", "incident_time"}
    if basis not in valid_bases:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail=f"Invalid time_basis '{time_basis}'. Allowed options: 'predicted_window', 'complaint_time', 'incident_time'."
        )

    start_dt = _parse_iso_timestamp(start_time, "start_time")
    end_dt = _parse_iso_timestamp(end_time, "end_time")

    if start_dt and end_dt and start_dt > end_dt:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail=f"Reversed time range: start_time ({start_time}) cannot be after end_time ({end_time})."
        )

    return start_dt, end_dt, basis


def _cluster_items(
    db: Session,
    clusters: List[LocationCluster],
    allowed_state: Optional[str] = None,
    user: Optional[User] = None,
    start_dt: Optional[datetime] = None,
    end_dt: Optional[datetime] = None,
    time_basis: str = "predicted_window",
    crime_category: Optional[str] = None,
) -> tuple:
    """
    Catalog geography plus current persisted case evidence, with multi-dimensional filtering.
    Returns (items: List[dict], evidence: Dict[int, dict])
    where evidence maps cluster_id -> dict of complaint_id -> {'prediction': pred, 'complaint': comp, 'locations': [loc, ...]}.
    """
    if not clusters:
        return [], {}
    cluster_ids = [cluster.id for cluster in clusters]
    atm_counts = dict(db.query(ATMLocation.cluster_id, func.count(ATMLocation.id)).filter(
        ATMLocation.cluster_id.in_(cluster_ids)
    ).group_by(ATMLocation.cluster_id).all())

    # Deterministically identify the latest operational prediction per complaint.
    # Primary key: analysis_purpose == 'OPERATIONAL' (explicit, persisted, never heuristic).
    # Secondary key: analysis_as_of IS NULL for backward-compat with old records.
    # Historical replays (analysis_purpose == 'HISTORICAL_REPLAY') never displace operational.
    latest_subq = (
        db.query(
            Prediction.id.label("pred_id"),
            func.row_number().over(
                partition_by=Prediction.complaint_id,
                order_by=(
                    (Prediction.analysis_purpose == "OPERATIONAL").desc(),
                    Prediction.analysis_as_of.is_(None).desc(),
                    Prediction.version_number.desc(),
                    Prediction.created_at.desc(),
                    Prediction.id.desc()
                )
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
    ]

    # Crime Category / Fraud Type filter
    if crime_category and crime_category.strip().upper() != "ALL":
        comp_filter.append(func.lower(Complaint.fraud_type) == crime_category.strip().lower())

    # Time filter based on time_basis
    if time_basis == "predicted_window":
        if start_dt:
            comp_filter.append(Prediction.predicted_window_end >= start_dt)
        if end_dt:
            comp_filter.append(Prediction.predicted_window_start <= end_dt)
        if not start_dt and not end_dt:
            comp_filter.append(Prediction.predicted_window_end > now_utc)
        elif not start_dt and end_dt and end_dt > now_utc:
            comp_filter.append(Prediction.predicted_window_end > now_utc)
    elif time_basis == "complaint_time":
        if start_dt:
            comp_filter.append(Complaint.reported_at >= start_dt)
        if end_dt:
            comp_filter.append(Complaint.reported_at <= end_dt)
        if not start_dt and not end_dt:
            comp_filter.append(Prediction.predicted_window_end > now_utc)
    elif time_basis == "incident_time":
        if start_dt:
            comp_filter.append(Complaint.incident_time >= start_dt)
        if end_dt:
            comp_filter.append(Complaint.incident_time <= end_dt)
        if not start_dt and not end_dt:
            comp_filter.append(Prediction.predicted_window_end > now_utc)

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
            "region_id": getattr(cluster, "region_id", None) or "delhi",
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
    region_id: Optional[str] = None,
    district: Optional[str] = None,
    risk_level: Optional[str] = None,
    crime_category: Optional[str] = None,
    time_basis: Optional[str] = "predicted_window",
    start_time: Optional[str] = None,
    end_time: Optional[str] = None,
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user)
):
    if not isinstance(current_user, User):
        raise HTTPException(status_code=401, detail="Authentication required")

    start_dt, end_dt, basis = _validate_time_filter(start_time, end_time, time_basis)

    query_clusters = _scope_cluster_query(db.query(LocationCluster), db, current_user)
    target_state = current_user.organization.state if current_user.organization and not is_national_scope(current_user) else "ALL"

    # Multi-region filtering (preserves server-side jurisdiction boundaries)
    if region_id and region_id != "ALL":
        r_clean = region_id.strip().lower()
        if r_clean == "delhi":
            query_clusters = query_clusters.filter(
                (LocationCluster.region_id == "delhi") |
                (func.lower(LocationCluster.state) == "delhi")
            )
        else:
            query_clusters = query_clusters.filter(LocationCluster.region_id == r_clean)

    if district and district != "ALL":
        query_clusters = query_clusters.filter(func.lower(LocationCluster.district) == district.strip().lower())

    clusters = query_clusters.order_by(LocationCluster.risk_score.desc()).all()

    hotspots, evidence = _cluster_items(
        db,
        clusters,
        allowed_state=target_state,
        user=current_user,
        start_dt=start_dt,
        end_dt=end_dt,
        time_basis=basis,
        crime_category=crime_category,
    )
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
        "region_id": region_id or "ALL",
        "data_basis": f"{target_state} catalog; active interception candidates reflect latest unexpired predictions with global complaint deduplication.",
        "filters_applied": {
            "region_id": region_id or "ALL",
            "district": district or "ALL",
            "risk_level": risk_level or "ALL",
            "crime_category": crime_category or "ALL",
            "time_basis": basis,
            "start_time": start_dt.isoformat() if start_dt else None,
            "end_time": end_dt.isoformat() if end_dt else None,
        }
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
    region_id: Optional[str] = None,
    district: Optional[str] = None,
    risk_level: Optional[str] = None,
    crime_category: Optional[str] = None,
    time_basis: Optional[str] = "predicted_window",
    start_time: Optional[str] = None,
    end_time: Optional[str] = None,
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user)
):
    start_dt, end_dt, basis = _validate_time_filter(start_time, end_time, time_basis)

    query = _scope_cluster_query(db.query(LocationCluster), db, current_user)
    target_state = current_user.organization.state if current_user.organization and not is_national_scope(current_user) else "ALL"

    if region_id and region_id != "ALL":
        r_clean = region_id.strip().lower()
        if r_clean == "delhi":
            query = query.filter(
                (LocationCluster.region_id == "delhi") |
                (func.lower(LocationCluster.state) == "delhi")
            )
        else:
            query = query.filter(LocationCluster.region_id == r_clean)

    if district and district != "ALL":
        query = query.filter(func.lower(LocationCluster.district) == district.strip().lower())

    clusters = query.order_by(LocationCluster.risk_score.desc()).all()
    items, _ = _cluster_items(
        db,
        clusters,
        allowed_state=target_state,
        user=current_user,
        start_dt=start_dt,
        end_dt=end_dt,
        time_basis=basis,
        crime_category=crime_category,
    )
    if risk_level and risk_level != "ALL":
        items = [item for item in items if item["risk_level"] == risk_level.upper() or item.get("operational_priority") == risk_level.upper()]
    return items


@router.get("/clusters/{id}", response_model=HotspotCluster)
def get_cluster(
    id: int,
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user),
    crime_category: Optional[str] = None,
    time_basis: Optional[str] = "predicted_window",
    start_time: Optional[str] = None,
    end_time: Optional[str] = None,
):
    if not isinstance(current_user, User):
        raise HTTPException(status_code=401, detail="Authentication required")

    start_dt, end_dt, basis = _validate_time_filter(start_time, end_time, time_basis)

    c = _scope_cluster_query(db.query(LocationCluster), db, current_user).filter(LocationCluster.id == id).first()
    if not c:
        raise HTTPException(status_code=404, detail=f"Cluster {id} not found or outside authorized officer jurisdiction.")

    target_state = current_user.organization.state if current_user.organization and not is_national_scope(current_user) else "ALL"
    items, _ = _cluster_items(
        db,
        [c],
        allowed_state=target_state,
        user=current_user,
        start_dt=start_dt,
        end_dt=end_dt,
        time_basis=basis,
        crime_category=crime_category,
    )
    if not items:
        raise HTTPException(status_code=404, detail=f"Cluster {id} not found")
    return items[0]


@router.get("/risk-map/prediction/{complaint_id}", response_model=PredictionResponse)
@router.get("/complaints/{complaint_id}/prediction-overlay", response_model=PredictionResponse)
def get_complaint_prediction_overlay(
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

    latest_pred = prediction_persistence_service.get_latest_operational_prediction(db, complaint.id)
    if not latest_pred:
        raise HTTPException(
            status_code=404,
            detail=f"No persisted prediction found for complaint {complaint.complaint_number}."
        )

    return _format_prediction_response(latest_pred, complaint)
