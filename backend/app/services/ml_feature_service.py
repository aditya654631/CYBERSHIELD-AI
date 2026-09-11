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
from sqlalchemy.orm import Session

from backend.app.models.models import Complaint, LocationCluster, Account
from backend.app.services.transaction_context_service import resolve_transaction_context
from backend.app.services.graph_service import build_complaint_graph
from ml.geo.candidate_generator import CandidateLocationGenerator, haversine_km
from ml.features.feature_pipeline import (
    feature_pipeline,
    FEATURE_COLUMNS_LOCATION_V3,
    FEATURE_COLUMNS_LOCATION_V3_1,
    FEATURE_COLUMNS_TIME,
    FRAUD_TYPE_MAP_V3,
    CHANNEL_MAP_V3
)
from backend.app.services.delhi_origin_resolver import resolve_delhi_origin

logger = logging.getLogger("cybershield.ml_feature_service")


def _complaint_to_dict(complaint: Complaint) -> Dict[str, Any]:
    """Converts a SQLAlchemy Complaint model instance into a safe dictionary with deterministic Delhi origin."""
    inc_dt = getattr(complaint, "incident_time", None) or getattr(complaint, "incident_timestamp", None)
    rep_dt = getattr(complaint, "reported_at", None)

    # Deterministic Delhi Origin Resolution if coordinates or zone need resolution
    v_lat = float(complaint.victim_lat) if complaint.victim_lat is not None else None
    v_lon = float(complaint.victim_lon) if complaint.victim_lon is not None else None
    v_dist = getattr(complaint, "victim_district", None) or getattr(complaint, "district", None)
    locality_str = getattr(complaint, "locality", None) or getattr(complaint, "victim_location", None) or ""

    if not v_dist or (v_dist == "CENTRAL_NEW_DELHI" and locality_str and "connaught" not in locality_str.lower() and "cp" not in locality_str.lower()):
        origin_res = resolve_delhi_origin(locality=locality_str, district=v_dist, lat=v_lat, lon=v_lon)
        if origin_res["resolved_district"] is not None:
            v_dist = origin_res["resolved_district"]
        if v_lat is None and origin_res["resolved_lat"] is not None and origin_res["provenance"] in ("LOCALITY_CLUSTER_MATCH", "LOCALITY_ALIAS_MATCH"):
            if "connaught" not in locality_str.lower():
                v_lat = origin_res["resolved_lat"]
                v_lon = origin_res["resolved_lon"]

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
        "victim_state": getattr(complaint, "victim_state", None) or getattr(complaint, "state", None) or "Delhi",
        "victim_district": v_dist,
        "victim_city": getattr(complaint, "victim_city", None) or getattr(complaint, "victim_location", None) or "Delhi",
        "victim_lat": v_lat,
        "victim_lon": v_lon,
        "status": getattr(complaint, "status", None) or getattr(complaint, "case_status", None),
        "risk_score": float(complaint.risk_score) if complaint.risk_score is not None else None,
        "risk_level": complaint.risk_level
    }


def _load_clusters_from_db(db: Session) -> List[Dict[str, Any]]:
    """Loads Delhi pilot location clusters strictly (excludes legacy MP clusters)."""
    clusters = (
        db.query(LocationCluster)
        .filter((LocationCluster.state == "Delhi") | (LocationCluster.city == "Delhi"))
        .order_by(LocationCluster.id.asc())
        .all()
    )
    res = []
    for c in clusters:
        res.append({
            "id": c.id,
            "name": c.cluster_name,
            "city": c.city or "Delhi",
            "state": c.state or "Delhi",
            "district": c.district,
            "zone": c.district,
            "lat": float(c.center_lat) if c.center_lat is not None else 28.6139,
            "lon": float(c.center_lon) if c.center_lon is not None else 77.2090,
            "atm_density": float(c.atm_count) if c.atm_count is not None else 15.0,
            "base_risk": float(c.risk_score) if c.risk_score is not None else 0.50,
            "historical_cashout_count": float(c.historical_fraud_count or 230.0),
            "historical_cashout_amount": float(c.historical_fraud_count or 230.0) * 50000.0
        })
    return res


def build_location_features(
    db: Session,
    complaint_id: int,
    top_k: int = 25,
    model_version: str = "v3.1"
) -> Dict[str, Any]:
    """
    Builds the candidate matrix for a given complaint.
    Supports:
    - "v3.1": 43 features (38 V3 features + 5 safe candidate-specific features, corridor-aware)
    - "v3": 38 features (legacy clean V3 baseline)
    """
    selected_feature_names = FEATURE_COLUMNS_LOCATION_V3_1 if model_version == "v3.1" else FEATURE_COLUMNS_LOCATION_V3

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
    context = resolve_transaction_context(db, complaint)
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

    # 2. Step 7 Dynamic NetworkX Graph
    graph_data = build_complaint_graph(db, complaint_id)
    graph_metrics = graph_data.get("metrics", {})

    # 3. Spatial Candidate Generation (Zero Target Prior)
    db_clusters = _load_clusters_from_db(db)
    cand_gen = CandidateLocationGenerator(clusters=db_clusters)
    if model_version == "v3.1":
        candidates = cand_gen.generate_candidates_for_complaint(
            complaint=comp_dict,
            top_k=top_k,
            transactions=transactions,
            terminal_zone=terminal_zone,
            all_tx_zones=all_tx_zones
        )
    else:
        candidates = cand_gen.generate_candidates_for_complaint(comp_dict, top_k=top_k)

    if not candidates:
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
    if model_version == "v3.1":
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
    complaint_id: int
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
    context = resolve_transaction_context(db, complaint)
    transactions = context.get("transactions", [])
    context_type = context.get("context_type", "EMPTY")
    source_scenario = context.get("source_scenario")

    # 2. Step 7 Dynamic NetworkX Graph
    graph_data = build_complaint_graph(db, complaint_id)
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
        "graph_edge_count": graph_metrics.get("edge_count", 0)
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
    top_k: int = 25
) -> Dict[str, Any]:
    """Convenience wrapper returning both Location V3 and Time V2 feature payloads."""
    loc_res = build_location_features(db, complaint_id, top_k=top_k)
    time_res = build_time_features(db, complaint_id)
    return {
        "location": loc_res,
        "time": time_res
    }
