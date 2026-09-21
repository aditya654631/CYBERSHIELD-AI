"""
CyberShield AI — DB-Driven ML Feature Pipeline Service
Phase 1 Step 8: Multi-Modal Feature Extraction Service

Produces model-ready feature matrices for:
1. Location Model V3 (38 candidate features, leakage-free, prediction-time-safe)
2. Time Model V2 (20 complaint features, prediction-time-safe)

Data Sources:
- PostgreSQL Complaint model
- Step 6 Transaction Context Resolver (resolve_transaction_context)
- Step 7 Dynamic NetworkX Graph Service (build_complaint_graph)
- Safe Geographic Candidate Generator (zero target knowledge)
- Frozen Training-Period Historical Baselines
"""

import math
import logging
from typing import Dict, Any, List, Optional, Tuple
import numpy as np
from sqlalchemy import func
from sqlalchemy.orm import Session

from backend.app.models.models import Complaint, LocationCluster, Account
from backend.app.services.transaction_context_service import resolve_transaction_context
from backend.app.services.graph_service import build_complaint_graph
from ml.geo.candidate_generator import CandidateLocationGenerator, haversine_km
from ml.features.feature_pipeline import (
    feature_pipeline,
    FEATURE_COLUMNS_LOCATION_V3,
    FEATURE_COLUMNS_LOCATION_V3_1,
    FEATURE_COLUMNS_LOCATION_V8_DEBIASED,
    FEATURE_COLUMNS_TIME,
    FRAUD_TYPE_MAP_V3,
    CHANNEL_MAP_V3
)
from backend.app.services.delhi_origin_resolver import resolve_delhi_origin

logger = logging.getLogger("cybershield.ml_feature_service")


def _complaint_to_dict(complaint: Complaint) -> Dict[str, Any]:
    """Converts a SQLAlchemy Complaint model instance into a safe dictionary with deterministic origin resolution."""
    inc_dt = getattr(complaint, "incident_time", None) or getattr(complaint, "incident_timestamp", None)
    rep_dt = getattr(complaint, "reported_at", None)

    v_lat = float(complaint.victim_lat) if complaint.victim_lat is not None else None
    v_lon = float(complaint.victim_lon) if complaint.victim_lon is not None else None
    v_dist = getattr(complaint, "victim_district", None) or getattr(complaint, "district", None)
    locality_str = getattr(complaint, "locality", None) or getattr(complaint, "victim_location", None) or ""
    c_state = getattr(complaint, "victim_state", None) or getattr(complaint, "state", None) or "Delhi"
    region_id = getattr(complaint, "region_id", None) or ("delhi" if str(c_state).strip().lower() in ("delhi", "new delhi") else None)

    # For Delhi cases, execute deterministic Delhi origin resolution
    if region_id == "delhi" or str(c_state).strip().lower() in ("delhi", "new delhi"):
        origin_res = resolve_delhi_origin(locality=locality_str, district=v_dist, lat=v_lat, lon=v_lon)
        if origin_res["resolved_district"] is not None:
            v_dist = origin_res["resolved_district"]
        if v_lat is None or v_lon is None:
            v_lat, v_lon = origin_res["resolved_lat"], origin_res["resolved_lon"]

    return {
        "complaint_id": complaint.id,
        "complaint_number": complaint.complaint_number,
        "fraud_type": complaint.fraud_type,
        "amount": float(complaint.amount) if complaint.amount is not None else None,
        "payment_channel": complaint.payment_channel,
        "incident_timestamp": inc_dt.isoformat() if inc_dt else None,
        "incident_time": inc_dt.isoformat() if inc_dt else None,
        "reported_at": rep_dt.isoformat() if rep_dt else None,
        "complaint_timestamp": rep_dt.isoformat() if rep_dt else None,
        "victim_state": c_state,
        "victim_district": v_dist,
        "victim_city": getattr(complaint, "victim_city", None) or getattr(complaint, "victim_location", None) or c_state,
        "victim_lat": v_lat,
        "victim_lon": v_lon,
        "region_id": region_id,
        "status": getattr(complaint, "status", None) or getattr(complaint, "case_status", None),
        "risk_score": float(complaint.risk_score) if complaint.risk_score is not None else None,
        "risk_level": complaint.risk_level
    }


def _load_clusters_from_db(db: Session, region_id: str = "delhi") -> List[Dict[str, Any]]:
    """
    Loads location clusters for a specific region.
    For Delhi (region_id='delhi'), strictly preserves the 60 Delhi pilot clusters and bounds.
    For non-Delhi regions, queries clusters registered under that region_id.
    """
    if region_id == "delhi":
        clusters = (
            db.query(LocationCluster)
            .filter(
                (LocationCluster.region_id == "delhi") |
                (func.lower(LocationCluster.state) == "delhi") |
                (func.lower(LocationCluster.city) == "delhi")
            )
            .order_by(LocationCluster.id.asc())
            .all()
        )
        res = []
        for c in clusters:
            if c.center_lat is None or c.center_lon is None:
                continue
            lat, lon = float(c.center_lat), float(c.center_lon)
            # Exact Delhi territorial bounding box
            if not (math.isfinite(lat) and math.isfinite(lon) and 28.38 <= lat <= 28.92 and 76.80 <= lon <= 77.45):
                continue
            res.append({
                "id": c.id,
                "name": c.cluster_name,
                "city": c.city or "Delhi",
                "state": c.state or "Delhi",
                "district": c.district,
                "zone": c.district,
                "lat": lat,
                "lon": lon,
                "atm_density": float(c.atm_count or 0),
                "base_risk": float(c.risk_score or 0.0),
                "historical_cashout_count": float(c.historical_fraud_count or 0),
                "historical_cashout_amount": float(c.historical_fraud_count or 0) * 50000.0
            })
        return res
    else:
        clusters = (
            db.query(LocationCluster)
            .filter(LocationCluster.region_id == region_id)
            .order_by(LocationCluster.id.asc())
            .all()
        )
        res = []
        for c in clusters:
            if c.center_lat is None or c.center_lon is None:
                continue
            lat, lon = float(c.center_lat), float(c.center_lon)
            if not (math.isfinite(lat) and math.isfinite(lon)):
                continue
            res.append({
                "id": c.id,
                "name": c.cluster_name,
                "city": c.city or "",
                "state": c.state or "",
                "district": c.district,
                "zone": c.district,
                "lat": lat,
                "lon": lon,
                "atm_density": float(c.atm_count or 0),
                "base_risk": float(c.risk_score or 0.0),
                "historical_cashout_count": float(c.historical_fraud_count or 0),
                "historical_cashout_amount": float(c.historical_fraud_count or 0) * 50000.0
            })
        return res


def build_location_features(
    db: Session,
    complaint_id: int,
    top_k: Optional[int] = 25,
    model_version: str = "v3.1",
    analysis_as_of: Optional[Any] = None
) -> Dict[str, Any]:
    """
    Builds the candidate matrix for a given complaint.
    Supports:
    - "v8_debiased": 40 features (leakage-free, causal money network corridors, evaluating all 60 Delhi clusters)
    - "v3.1": 43 features (38 V3 features + 5 safe candidate-specific features, corridor-aware)
    - "v3": 38 features (legacy clean V3 baseline)
    """
    if model_version == "v8_debiased":
        selected_feature_names = FEATURE_COLUMNS_LOCATION_V8_DEBIASED
    elif model_version == "v3.1":
        selected_feature_names = FEATURE_COLUMNS_LOCATION_V3_1
    else:
        selected_feature_names = FEATURE_COLUMNS_LOCATION_V3

    complaint = db.query(Complaint).filter(Complaint.id == complaint_id).first()
    if not complaint:
        return {
            "status": "COMPLAINT_NOT_FOUND",
            "feature_names": selected_feature_names,
            "feature_count": len(selected_feature_names),
            "candidate_rows": np.empty((0, len(selected_feature_names)), dtype=np.float32),
            "candidates": [],
            "missing_features": [],
            "provenance": {"complaint_id": complaint_id, "error": "Complaint not found in database"},
            "model_contract_version": model_version
        }

    comp_dict = _complaint_to_dict(complaint)

    # 1. Step 6 Transaction Context
    context = resolve_transaction_context(db, complaint, analysis_as_of=analysis_as_of)
    transactions = context.get("transactions", [])
    context_type = context.get("context_type", "EMPTY")
    source_scenario = context.get("source_scenario")

    # Resolve observed account geography from transactions
    terminal_zone = None
    all_tx_zones = set()
    if transactions:
        acc_ids = set()
        for tx in transactions:
            rid = getattr(tx, "receiver_account_id", None)
            if rid is not None:
                acc_ids.add(rid)
        if acc_ids:
            accounts_map = {a.id: a for a in db.query(Account).filter(Account.id.in_(acc_ids)).all()}
            max_h = max(int(getattr(t, "hop_number", 1) or 1) for t in transactions)
            term_txs = [t for t in transactions if int(getattr(t, "hop_number", 1) or 1) == max_h]
            if term_txs:
                best_t = max(term_txs, key=lambda t: float(getattr(t, "amount", 0.0) or 0.0))
                term_acc = accounts_map.get(best_t.receiver_account_id)
                if term_acc and term_acc.district:
                    terminal_zone = str(term_acc.district)
            for acc in accounts_map.values():
                if acc.district:
                    all_tx_zones.add(str(acc.district))

    # 2. Step 7 Dynamic NetworkX Graph (strictly include_outcomes=False for prediction features)
    graph_data = build_complaint_graph(db, complaint_id, analysis_as_of=analysis_as_of, include_outcomes=False)
    graph_metrics = graph_data.get("metrics", {})

    # 3. Spatial Candidate Generation (Zero Target Prior)
    region_id = comp_dict.get("region_id") or "delhi"
    if region_id != "delhi":
        from backend.app.services.geography_catalog_service import get_region_by_id
        r_obj = get_region_by_id(db, region_id)
        if not r_obj or r_obj.model_support_status != "MODEL_SUPPORTED":
            return {
                "status": "UNSUPPORTED_REGION",
                "feature_names": selected_feature_names,
                "feature_count": len(selected_feature_names),
                "candidate_rows": np.empty((0, len(selected_feature_names)), dtype=np.float32),
                "candidates": [],
                "missing_features": ["candidates"],
                "provenance": {
                    "complaint_id": complaint_id,
                    "region_id": region_id,
                    "error": f"Model inference unsupported for region '{region_id}'."
                },
                "model_contract_version": model_version
            }

    db_clusters = _load_clusters_from_db(db, region_id=region_id)
    cand_gen = CandidateLocationGenerator(clusters=db_clusters)
    if model_version in ("v8_debiased", "v3.1", "v7_compat", "v4"):
        candidates = cand_gen.generate_candidates_for_complaint(
            complaint=comp_dict,
            top_k=top_k,
            transactions=transactions,
            terminal_zone=terminal_zone,
            all_tx_zones=all_tx_zones
        )
    else:
        candidates = cand_gen.generate_candidates_for_complaint(comp_dict, top_k=top_k)

    if len(candidates) < 3:
        return {
            "status": "INSUFFICIENT_GEO_DATA",
            "feature_names": selected_feature_names,
            "feature_count": len(selected_feature_names),
            "candidate_rows": np.empty((0, len(selected_feature_names)), dtype=np.float32),
            "candidates": [],
            "missing_features": ["candidates"],
            "provenance": {"complaint_id": complaint_id, "context_type": context_type},
            "model_contract_version": model_version
        }

    # 4. Multimodal Feature Matrix Construction
    if model_version == "v8_debiased":
        X_location, _, feature_names, _ = feature_pipeline.build_candidate_matrix_v8_debiased(
            complaint=comp_dict,
            candidates=candidates,
            transactions=transactions,
            graph_metrics=graph_metrics,
            terminal_zone=terminal_zone,
            all_tx_zones=all_tx_zones
        )
    elif model_version in ("v3.1", "v7_compat", "v4"):
        X_location, _, feature_names, _ = feature_pipeline.build_candidate_matrix_v3_1(
            complaint=comp_dict,
            candidates=candidates,
            transactions=transactions,
            graph_metrics=graph_metrics,
            terminal_zone=terminal_zone,
            all_tx_zones=all_tx_zones
        )
    else:
        X_location, _, feature_names, _ = feature_pipeline.build_candidate_matrix_v3(
            complaint=comp_dict,
            candidates=candidates,
            transactions=transactions,
            graph_metrics=graph_metrics
        )

    # Identify missing features (NaN values)
    missing = []
    if X_location.shape[0] > 0:
        for idx, col in enumerate(feature_names):
            if np.isnan(X_location[:, idx]).any():
                missing.append(col)

    # Check status
    if comp_dict["amount"] is None and comp_dict["incident_timestamp"] is None and context_type == "EMPTY":
        status = "INSUFFICIENT_DATA"
    else:
        status = "SUCCESS"

    provenance = {
        "complaint_id": complaint.id,
        "complaint_number": complaint.complaint_number,
        "context_type": context_type,
        "source_scenario": source_scenario,
        "transaction_count": len(transactions),
        "graph_node_count": graph_metrics.get("node_count", 0),
        "graph_edge_count": graph_metrics.get("edge_count", 0),
        "candidate_count": len(candidates),
        "top_k_requested": top_k,
        "cluster_database_source": "PostgreSQL LocationCluster",
        "terminal_zone": terminal_zone,
        "all_tx_zones": list(all_tx_zones),
        "leakage_features_removed": ["is_mule_corridor", "distance_from_high_risk_account"]
    }

    return {
        "status": status,
        "feature_names": feature_names,
        "feature_count": len(feature_names),
        "candidate_rows": X_location,
        "candidates": candidates,
        "missing_features": missing,
        "provenance": provenance,
        "model_contract_version": model_version
    }


def build_time_features(
    db: Session,
    complaint_id: int,
    analysis_as_of: Optional[Any] = None
) -> Dict[str, Any]:
    """
    Builds the 20-feature Time Model V2 vector for a given complaint.
    Returns:
        {
            "status": "SUCCESS" | "INSUFFICIENT_DATA" | "COMPLAINT_NOT_FOUND",
            "feature_names": List[str], # length 20
            "feature_count": int,       # 20
            "values": np.ndarray,       # (20,)
            "missing_features": List[str],
            "provenance": Dict[str, Any],
            "model_contract_version": "v2"
        }
    """
    complaint = db.query(Complaint).filter(Complaint.id == complaint_id).first()
    if not complaint:
        return {
            "status": "COMPLAINT_NOT_FOUND",
            "feature_names": FEATURE_COLUMNS_TIME,
            "feature_count": len(FEATURE_COLUMNS_TIME),
            "values": np.full(len(FEATURE_COLUMNS_TIME), np.nan, dtype=np.float32),
            "missing_features": FEATURE_COLUMNS_TIME,
            "provenance": {"complaint_id": complaint_id, "error": "Complaint not found"},
            "model_contract_version": "v2"
        }

    comp_dict = _complaint_to_dict(complaint)

    # 1. Step 6 Transaction Context
    context = resolve_transaction_context(db, complaint, analysis_as_of=analysis_as_of)
    transactions = context.get("transactions", [])
    context_type = context.get("context_type", "EMPTY")
    source_scenario = context.get("source_scenario")

    # 2. Step 7 Dynamic NetworkX Graph (strictly include_outcomes=False for prediction features)
    graph_data = build_complaint_graph(db, complaint_id, analysis_as_of=analysis_as_of, include_outcomes=False)
    graph_metrics = graph_data.get("metrics", {})

    # 3. Multimodal Time Feature Extraction
    _, X_time, _, time_feature_names = feature_pipeline.build_candidate_matrix_v3(
        complaint=comp_dict,
        candidates=[],
        transactions=transactions,
        graph_metrics=graph_metrics
    )

    values = X_time[0]
    missing = [time_feature_names[i] for i, v in enumerate(values) if np.isnan(v)]

    if comp_dict["amount"] is None and comp_dict["incident_timestamp"] is None and context_type == "EMPTY":
        status = "INSUFFICIENT_DATA"
    else:
        status = "SUCCESS"

    provenance = {
        "complaint_id": complaint.id,
        "complaint_number": complaint.complaint_number,
        "context_type": context_type,
        "source_scenario": source_scenario,
        "transaction_count": len(transactions),
        "graph_node_count": graph_metrics.get("node_count", 0),
        "graph_edge_count": graph_metrics.get("edge_count", 0),
        "analysis_as_of": context.get("analysis_as_of")
    }

    return {
        "status": status,
        "feature_names": time_feature_names,
        "feature_count": len(time_feature_names),
        "values": values,
        "missing_features": missing,
        "provenance": provenance,
        "model_contract_version": "v2"
    }


def build_multimodal_features(
    db: Session,
    complaint_id: int,
    top_k: int = 25,
    analysis_as_of: Optional[Any] = None
) -> Dict[str, Any]:
    """Convenience wrapper returning both Location V3 and Time V2 feature payloads."""
    loc_res = build_location_features(db, complaint_id, top_k=top_k, analysis_as_of=analysis_as_of)
    time_res = build_time_features(db, complaint_id, analysis_as_of=analysis_as_of)
    return {
        "location": loc_res,
        "time": time_res
    }
