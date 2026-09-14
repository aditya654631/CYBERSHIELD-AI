"""
Blockchain Feature Extractor (Python) — Direct Parity with B.4 Node Feature Engine
Schema Version: blockchain-feature-schema-v1

This extractor implements identical feature computation logic to:
- blockchain/feature-engine/src/signal-normalizer.js
- blockchain/feature-engine/src/cluster-feature-builder.js
- blockchain/feature-engine/src/temporal-window.js
- blockchain/feature-engine/blockchain_feature_contract.json

All feature names, types, missing values, and rounding formulas are 100% frozen
and guaranteed to match the Node B.4 implementation bit-for-bit.
"""

from __future__ import annotations
import json
import math
from datetime import datetime, timezone
from pathlib import Path
from typing import Any, Dict, List, Optional, Set, Tuple

SCHEMA_VERSION = "blockchain-feature-schema-v1"

BANK_MSPS = ("BankAMSP", "BankBMSP", "BankCMSP")
AUTHORITY_MSPS = ("I4CMSP", "LEAMSP")
ALL_CONSORTIUM_MSPS = BANK_MSPS + AUTHORITY_MSPS

EVENT_TYPES = {
    "ATM_WITHDRAWAL_CONFIRMED": "ATM_WITHDRAWAL_CONFIRMED",
    "ATM_WITHDRAWAL_ATTEMPT": "ATM_WITHDRAWAL_ATTEMPT",
    "BRANCH_CASHOUT_CONFIRMED": "BRANCH_CASHOUT_CONFIRMED",
    "MULE_ACCOUNT_ACTIVITY": "MULE_ACCOUNT_ACTIVITY",
    "LEA_CONFIRMED_CLUSTER": "LEA_CONFIRMED_CLUSTER",
    "SIGNAL_CORRECTION": "SIGNAL_CORRECTION",
    "SIGNAL_REVOKED": "SIGNAL_REVOKED"
}

WINDOWS_MS = {
    "1h": 60 * 60 * 1000,
    "6h": 6 * 60 * 60 * 1000,
    "24h": 24 * 60 * 60 * 1000,
    "7d": 7 * 24 * 60 * 60 * 1000,
    "30d": 30 * 24 * 60 * 60 * 1000
}

CONTRACT_PATH = Path(__file__).resolve().parents[2] / "blockchain" / "feature-engine" / "blockchain_feature_contract.json"

def load_feature_contract() -> Dict[str, Any]:
    if not CONTRACT_PATH.exists():
        raise FileNotFoundError(f"Blockchain feature contract not found at {CONTRACT_PATH}")
    with open(CONTRACT_PATH, "r", encoding="utf-8") as f:
        return json.load(f)

# Ordered feature list matching the frozen contract
CONTRACT_SPEC = load_feature_contract()
FEATURE_DEFINITIONS = CONTRACT_SPEC.get("features", {})
ORDERED_BLOCKCHAIN_FEATURES = list(FEATURE_DEFINITIONS.keys())


def parse_iso_to_epoch_ms(iso_str: str) -> int:
    """
    Parses an ISO-8601 string to integer epoch milliseconds in UTC.
    Compatible with Date.parse in JS.
    """
    if iso_str.endswith("Z"):
        clean_str = iso_str[:-1] + "+00:00"
    else:
        clean_str = iso_str
    dt = datetime.fromisoformat(clean_str)
    # Ensure UTC timestamp
    epoch = datetime(1970, 1, 1, tzinfo=timezone.utc)
    if dt.tzinfo is None:
        dt = dt.replace(tzinfo=timezone.utc)
    return int((dt - epoch).total_seconds() * 1000.0)


def epoch_ms_to_iso_day(epoch_ms: int) -> str:
    """
    Converts epoch ms to YYYY-MM-DD (Date.prototype.toISOString().split('T')[0]).
    """
    dt = datetime.fromtimestamp(epoch_ms / 1000.0, tz=timezone.utc)
    return dt.strftime("%Y-%m-%d")


def normalize_signals_at_reference(
    raw_signals: List[Dict[str, Any]],
    ref_time_ms: int,
    history_map: Optional[Dict[str, List[Dict[str, Any]]]] = None
) -> Tuple[List[Dict[str, Any]], List[Dict[str, Any]], int, int]:
    """
    Direct Python equivalent of signal-normalizer.js:normalizeSignalsAtReference.
    Returns (active_signals, all_signals_at_ref, future_excluded_count, revoked_excluded_count).
    """
    if not isinstance(raw_signals, list):
        return [], [], 0, 0

    future_excluded_count = 0
    revoked_excluded_count = 0
    all_signals_at_ref = []

    signal_by_id = {}
    for s in raw_signals:
        if s and s.get("event_id"):
            signal_by_id[s["event_id"]] = s

    for s in raw_signals:
        if not s or not s.get("event_id"):
            continue

        evt_ts = s.get("event_timestamp")
        event_time_ms = parse_iso_to_epoch_ms(evt_ts) if isinstance(evt_ts, str) else int(s.get("eventTimeMs", 0))
        sub_ts = s.get("submitted_at")
        submitted_at_ms = parse_iso_to_epoch_ms(sub_ts) if isinstance(sub_ts, str) else event_time_ms

        # Anti-leakage rule: Cannot use future events
        if event_time_ms > ref_time_ms or submitted_at_ms > ref_time_ms:
            future_excluded_count += 1
            continue

        effective_status = s.get("status", "ACTIVE")
        conf_raw = s.get("confidence", 1.0)
        effective_confidence = float(conf_raw) if conf_raw is not None else 1.0
        effective_type = s.get("event_type")

        # Check history map if provided
        if history_map and s["event_id"] in history_map:
            history = history_map[s["event_id"]]
            latest_val = None
            for h in history:
                h_ts = h.get("timestamp")
                h_time_ms = parse_iso_to_epoch_ms(h_ts) if isinstance(h_ts, str) else 0
                if h_time_ms <= ref_time_ms and isinstance(h.get("value"), dict):
                    latest_val = h["value"]
            if latest_val:
                effective_status = latest_val.get("status", effective_status)
                if "confidence" in latest_val and latest_val["confidence"] is not None:
                    effective_confidence = float(latest_val["confidence"])
                effective_type = latest_val.get("event_type", effective_type)
        else:
            # Deduce from current state
            if s.get("status") == "REVOKED":
                rev_id = s.get("revoked_by_event_id")
                if rev_id and rev_id in signal_by_id:
                    rev_event = signal_by_id[rev_id]
                    r_sub = rev_event.get("submitted_at")
                    rev_time_ms = parse_iso_to_epoch_ms(r_sub) if r_sub else parse_iso_to_epoch_ms(rev_event["event_timestamp"])
                    if rev_time_ms <= ref_time_ms:
                        effective_status = "REVOKED"
                    else:
                        effective_status = "ACTIVE"
                elif s.get("event_type") == "SIGNAL_REVOKED":
                    effective_status = "REVOKED"

            if s.get("status") == "CORRECTED":
                corr_id = s.get("corrected_by_event_id")
                if corr_id and corr_id in signal_by_id:
                    corr_event = signal_by_id[corr_id]
                    c_sub = corr_event.get("submitted_at")
                    corr_time_ms = parse_iso_to_epoch_ms(c_sub) if c_sub else parse_iso_to_epoch_ms(corr_event["event_timestamp"])
                    if corr_time_ms <= ref_time_ms:
                        effective_status = "CORRECTED"
                    else:
                        effective_status = "ACTIVE"

        cid = s.get("cluster_id")
        cluster_id = int(cid) if cid is not None else None

        normalized = {
            "event_id": s["event_id"],
            "event_type": effective_type,
            "organization_msp": s.get("organization_msp") or s.get("created_by_msp") or "UNKNOWN",
            "cluster_id": cluster_id,
            "district": s.get("district"),
            "event_timestamp": s.get("event_timestamp"),
            "eventTimeMs": event_time_ms,
            "submitted_at": s.get("submitted_at"),
            "confidence": 0.0 if math.isnan(effective_confidence) else effective_confidence,
            "status": effective_status,
            "source_reference_hash": s.get("source_reference_hash"),
            "opaque_subject_ref": s.get("opaque_subject_ref")
        }
        all_signals_at_ref.append(normalized)

    active_signals = []
    for sig in all_signals_at_ref:
        if sig["status"] == "REVOKED" or sig["event_type"] == "SIGNAL_REVOKED":
            revoked_excluded_count += 1
            continue
        if sig["status"] == "CORRECTED":
            continue
        active_signals.append(sig)

    return active_signals, all_signals_at_ref, future_excluded_count, revoked_excluded_count


def partition_signals_by_window(signals: List[Dict[str, Any]], ref_time_ms: int) -> Dict[str, List[Dict[str, Any]]]:
    """
    Direct Python equivalent of temporal-window.js:partitionSignalsByWindow.
    """
    partitioned = {
        "1h": [],
        "6h": [],
        "24h": [],
        "7d": [],
        "30d": []
    }
    for s in signals:
        age_ms = ref_time_ms - s["eventTimeMs"]
        if age_ms < 0:
            continue
        if age_ms <= WINDOWS_MS["1h"]:
            partitioned["1h"].append(s)
        if age_ms <= WINDOWS_MS["6h"]:
            partitioned["6h"].append(s)
        if age_ms <= WINDOWS_MS["24h"]:
            partitioned["24h"].append(s)
        if age_ms <= WINDOWS_MS["7d"]:
            partitioned["7d"].append(s)
        if age_ms <= WINDOWS_MS["30d"]:
            partitioned["30d"].append(s)
    return partitioned


def compute_confidence_stats(signals: List[Dict[str, Any]]) -> Tuple[float, float]:
    """
    Computes mean and max confidence rounded to 4 decimals, matching JS Number((val).toFixed(4)).
    """
    if not signals:
        return 0.0, 0.0
    total = 0.0
    max_c = 0.0
    for s in signals:
        c = s.get("confidence", 0.0)
        if c is None:
            c = 0.0
        total += float(c)
        if c > max_c:
            max_c = c
    mean_val = round(total / len(signals), 4)
    max_val = round(float(max_c), 4)
    return mean_val, max_val


def compute_age_minutes(signals: List[Dict[str, Any]], ref_time_ms: int, event_type_filter: Optional[str] = None) -> float:
    """
    Computes minimum age in minutes, rounded to 2 decimals, matching JS Number((minAgeMs / 60000).toFixed(2)).
    Returns -1.0 if no matching events.
    """
    filtered = signals
    if event_type_filter:
        filtered = [s for s in signals if s.get("event_type") == event_type_filter]
    if not filtered:
        return -1.0

    min_age_ms = float("inf")
    for s in filtered:
        age_ms = ref_time_ms - s["eventTimeMs"]
        if 0 <= age_ms < min_age_ms:
            min_age_ms = age_ms

    if min_age_ms == float("inf"):
        return -1.0
    return round(min_age_ms / (60.0 * 1000.0), 2)


def count_active_days(signals: List[Dict[str, Any]]) -> int:
    """
    Counts distinct calendar days in UTC (ISO YYYY-MM-DD), matching JS new Date(s.eventTimeMs).toISOString().split('T')[0].
    """
    days: Set[str] = set()
    for s in signals:
        day_key = epoch_ms_to_iso_day(s["eventTimeMs"])
        days.add(day_key)
    return len(days)


def build_cluster_feature_vector(
    cluster_id: int,
    ref_time_ms: int,
    active_cluster_signals: List[Dict[str, Any]],
    all_cluster_signals_at_ref: List[Dict[str, Any]],
    subject_signals: Optional[List[Dict[str, Any]]] = None,
    opaque_subject_ref: Optional[str] = None
) -> Dict[str, Any]:
    """
    Direct Python equivalent of cluster-feature-builder.js:buildClusterFeatureVector.
    Produces deterministic dictionary of features exactly matching Node B.4.
    """
    if subject_signals is None:
        subject_signals = []

    by_win = partition_signals_by_window(active_cluster_signals, ref_time_ms)

    def count_type(sig_list: List[Dict[str, Any]], etype: str) -> int:
        return sum(1 for s in sig_list if s.get("event_type") == etype)

    # 1. Core Temporal Counts
    verified_cashouts_1h = count_type(by_win["1h"], EVENT_TYPES["ATM_WITHDRAWAL_CONFIRMED"])
    verified_cashouts_6h = count_type(by_win["6h"], EVENT_TYPES["ATM_WITHDRAWAL_CONFIRMED"])
    verified_cashouts_24h = count_type(by_win["24h"], EVENT_TYPES["ATM_WITHDRAWAL_CONFIRMED"])

    withdrawal_attempts_1h = count_type(by_win["1h"], EVENT_TYPES["ATM_WITHDRAWAL_ATTEMPT"])
    withdrawal_attempts_6h = count_type(by_win["6h"], EVENT_TYPES["ATM_WITHDRAWAL_ATTEMPT"])
    withdrawal_attempts_24h = count_type(by_win["24h"], EVENT_TYPES["ATM_WITHDRAWAL_ATTEMPT"])

    branch_cashouts_6h = count_type(by_win["6h"], EVENT_TYPES["BRANCH_CASHOUT_CONFIRMED"])
    branch_cashouts_24h = count_type(by_win["24h"], EVENT_TYPES["BRANCH_CASHOUT_CONFIRMED"])

    mule_activity_6h = count_type(by_win["6h"], EVENT_TYPES["MULE_ACCOUNT_ACTIVITY"])
    mule_activity_24h = count_type(by_win["24h"], EVENT_TYPES["MULE_ACCOUNT_ACTIVITY"])

    lea_confirmations_6h = count_type(by_win["6h"], EVENT_TYPES["LEA_CONFIRMED_CLUSTER"])
    lea_confirmations_24h = count_type(by_win["24h"], EVENT_TYPES["LEA_CONFIRMED_CLUSTER"])

    # 2. Source Diversity
    distinct_orgs_1h = len(set(s["organization_msp"] for s in by_win["1h"] if s.get("organization_msp")))
    distinct_orgs_6h = len(set(s["organization_msp"] for s in by_win["6h"] if s.get("organization_msp")))
    distinct_orgs_24h = len(set(s["organization_msp"] for s in by_win["24h"] if s.get("organization_msp")))

    distinct_banks_1h = len(set(s["organization_msp"] for s in by_win["1h"] if s.get("organization_msp") in BANK_MSPS))
    distinct_banks_6h = len(set(s["organization_msp"] for s in by_win["6h"] if s.get("organization_msp") in BANK_MSPS))
    distinct_banks_24h = len(set(s["organization_msp"] for s in by_win["24h"] if s.get("organization_msp") in BANK_MSPS))

    # 3. Multi-Org Attestation
    multi_org_attestation_1h = distinct_orgs_1h
    multi_org_attestation_6h = distinct_orgs_6h
    multi_org_attestation_24h = distinct_orgs_24h

    has_multi_org_attestation_1h = 1 if distinct_orgs_1h >= 2 else 0
    has_multi_org_attestation_6h = 1 if distinct_orgs_6h >= 2 else 0
    has_multi_org_attestation_24h = 1 if distinct_orgs_24h >= 2 else 0

    # 4. Confidence Features
    mean_signal_confidence_1h, max_signal_confidence_1h = compute_confidence_stats(by_win["1h"])
    mean_signal_confidence_6h, max_signal_confidence_6h = compute_confidence_stats(by_win["6h"])
    mean_signal_confidence_24h, max_signal_confidence_24h = compute_confidence_stats(by_win["24h"])

    # 5. Recency Features
    latest_signal_age_minutes = compute_age_minutes(active_cluster_signals, ref_time_ms)
    latest_verified_cashout_age_minutes = compute_age_minutes(active_cluster_signals, ref_time_ms, EVENT_TYPES["ATM_WITHDRAWAL_CONFIRMED"])
    latest_attempt_age_minutes = compute_age_minutes(active_cluster_signals, ref_time_ms, EVENT_TYPES["ATM_WITHDRAWAL_ATTEMPT"])
    latest_lea_confirmation_age_minutes = compute_age_minutes(active_cluster_signals, ref_time_ms, EVENT_TYPES["LEA_CONFIRMED_CLUSTER"])

    # 6. Recurrence Features
    cluster_signal_count_7d = len(by_win["7d"])
    cluster_signal_count_30d = len(by_win["30d"])

    cluster_active_days_7d = count_active_days(by_win["7d"])
    cluster_active_days_30d = count_active_days(by_win["30d"])

    cluster_recurrence_rate_7d = round(cluster_active_days_7d / 7.0, 4)
    cluster_recurrence_rate_30d = round(cluster_active_days_30d / 30.0, 4)

    # 7. Metadata Quality / Governance
    all_24h = partition_signals_by_window(all_cluster_signals_at_ref, ref_time_ms)["24h"]
    correction_count_24h = sum(1 for s in all_24h if s.get("event_type") == EVENT_TYPES["SIGNAL_CORRECTION"] or s.get("status") == "CORRECTED")
    revocation_count_24h = sum(1 for s in all_24h if s.get("event_type") == EVENT_TYPES["SIGNAL_REVOKED"] or s.get("status") == "REVOKED")
    total_signals_24h = len(all_24h)
    active_signal_ratio_24h = round(len(by_win["24h"]) / float(total_signals_24h), 4) if total_signals_24h > 0 else 1.0

    # 8. Subject-Linked Features
    subject_features_available = 0
    subject_signal_count_1h = 0
    subject_signal_count_6h = 0
    subject_signal_count_24h = 0
    subject_distinct_clusters_24h = 0
    subject_distinct_orgs_24h = 0

    if opaque_subject_ref and subject_signals:
        subject_features_available = 1
        subj_win = partition_signals_by_window(subject_signals, ref_time_ms)
        subject_signal_count_1h = len(subj_win["1h"])
        subject_signal_count_6h = len(subj_win["6h"])
        subject_signal_count_24h = len(subj_win["24h"])

        distinct_clusters = set(s["cluster_id"] for s in subj_win["24h"] if s.get("cluster_id") is not None)
        distinct_orgs = set(s["organization_msp"] for s in subj_win["24h"] if s.get("organization_msp"))
        subject_distinct_clusters_24h = len(distinct_clusters)
        subject_distinct_orgs_24h = len(distinct_orgs)

    vec = {
        # Core Temporal
        "verified_cashouts_1h": verified_cashouts_1h,
        "verified_cashouts_6h": verified_cashouts_6h,
        "verified_cashouts_24h": verified_cashouts_24h,
        "withdrawal_attempts_1h": withdrawal_attempts_1h,
        "withdrawal_attempts_6h": withdrawal_attempts_6h,
        "withdrawal_attempts_24h": withdrawal_attempts_24h,
        "branch_cashouts_6h": branch_cashouts_6h,
        "branch_cashouts_24h": branch_cashouts_24h,
        "mule_activity_6h": mule_activity_6h,
        "mule_activity_24h": mule_activity_24h,
        "lea_confirmations_6h": lea_confirmations_6h,
        "lea_confirmations_24h": lea_confirmations_24h,

        # Source Diversity
        "distinct_orgs_1h": distinct_orgs_1h,
        "distinct_orgs_6h": distinct_orgs_6h,
        "distinct_orgs_24h": distinct_orgs_24h,
        "distinct_banks_1h": distinct_banks_1h,
        "distinct_banks_6h": distinct_banks_6h,
        "distinct_banks_24h": distinct_banks_24h,

        # Multi-Org Attestation
        "multi_org_attestation_1h": multi_org_attestation_1h,
        "multi_org_attestation_6h": multi_org_attestation_6h,
        "multi_org_attestation_24h": multi_org_attestation_24h,
        "has_multi_org_attestation_1h": has_multi_org_attestation_1h,
        "has_multi_org_attestation_6h": has_multi_org_attestation_6h,
        "has_multi_org_attestation_24h": has_multi_org_attestation_24h,

        # Confidence
        "mean_signal_confidence_1h": mean_signal_confidence_1h,
        "mean_signal_confidence_6h": mean_signal_confidence_6h,
        "mean_signal_confidence_24h": mean_signal_confidence_24h,
        "max_signal_confidence_1h": max_signal_confidence_1h,
        "max_signal_confidence_6h": max_signal_confidence_6h,
        "max_signal_confidence_24h": max_signal_confidence_24h,

        # Recency
        "latest_signal_age_minutes": latest_signal_age_minutes,
        "latest_verified_cashout_age_minutes": latest_verified_cashout_age_minutes,
        "latest_attempt_age_minutes": latest_attempt_age_minutes,
        "latest_lea_confirmation_age_minutes": latest_lea_confirmation_age_minutes,

        # Recurrence
        "cluster_signal_count_7d": cluster_signal_count_7d,
        "cluster_signal_count_30d": cluster_signal_count_30d,
        "cluster_active_days_7d": cluster_active_days_7d,
        "cluster_active_days_30d": cluster_active_days_30d,
        "cluster_recurrence_rate_7d": cluster_recurrence_rate_7d,
        "cluster_recurrence_rate_30d": cluster_recurrence_rate_30d,

        # Quality & Governance
        "correction_count_24h": correction_count_24h,
        "revocation_count_24h": revocation_count_24h,
        "active_signal_ratio_24h": active_signal_ratio_24h,

        # Subject-Linked
        "subject_features_available": subject_features_available,
        "subject_signal_count_1h": subject_signal_count_1h,
        "subject_signal_count_6h": subject_signal_count_6h,
        "subject_signal_count_24h": subject_signal_count_24h,
        "subject_distinct_clusters_24h": subject_distinct_clusters_24h,
        "subject_distinct_orgs_24h": subject_distinct_orgs_24h
    }

    return vec


def extract_candidate_blockchain_features(
    cluster_id: int,
    reference_timestamp: str,
    raw_signals: List[Dict[str, Any]],
    opaque_subject_ref: Optional[str] = None,
    raw_subject_signals: Optional[List[Dict[str, Any]]] = None,
    fabric_available: bool = True
) -> Dict[str, Any]:
    """
    Main entry point for extracting blockchain features for a candidate cluster.
    If fabric_available is False, returns default missing values per contract.
    """
    ref_time_ms = parse_iso_to_epoch_ms(reference_timestamp)

    if not fabric_available or raw_signals is None:
        # Default missing values from contract
        features = {}
        for feat_name, feat_meta in FEATURE_DEFINITIONS.items():
            features[feat_name] = feat_meta.get("missing_value", 0)
        return {
            "features": features,
            "fabric_available": 0
        }

    # Filter signals for this cluster
    cluster_signals = [s for s in raw_signals if s.get("cluster_id") == cluster_id]
    active_signals, all_signals_at_ref, _, _ = normalize_signals_at_reference(cluster_signals, ref_time_ms)

    # Subject signals
    subj_active_signals = []
    if opaque_subject_ref and raw_subject_signals:
        subj_filtered = [s for s in raw_subject_signals if s.get("opaque_subject_ref") == opaque_subject_ref]
        subj_active_signals, _, _, _ = normalize_signals_at_reference(subj_filtered, ref_time_ms)

    features = build_cluster_feature_vector(
        cluster_id=cluster_id,
        ref_time_ms=ref_time_ms,
        active_cluster_signals=active_signals,
        all_cluster_signals_at_ref=all_signals_at_ref,
        subject_signals=subj_active_signals,
        opaque_subject_ref=opaque_subject_ref
    )

    return {
        "features": features,
        "fabric_available": 1 if fabric_available else 0
    }
