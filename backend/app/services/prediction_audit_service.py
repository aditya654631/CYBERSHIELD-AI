"""
CyberShield AI — Phase B.5: Tamper-Evident Prediction Audit Service (Python Client)

Handles canonical hashing, ledger anchor submission, and verification
against Hyperledger Fabric network via the Fabric Gateway service.

Guarantees:
1. Deterministic canonical hash matching schema 'prediction-audit-v1'.
2. Privacy preservation: raw PII/complaint data is never sent to ledger.
3. Fault-isolation: Failure of Fabric anchor never raises or breaks ML prediction.
4. Non-blocking: returns anchor status truthfully (ANCHORED, PENDING, ANCHOR_FAILED).
"""

import os
import json
import logging
import hashlib
from datetime import datetime, timezone
from typing import Dict, Any, Optional, List
import requests

logger = logging.getLogger("cybershield.prediction_audit")

GATEWAY_BASE_URL = os.environ.get("FABRIC_GATEWAY_URL", "http://localhost:4000/api/v1")
SCHEMA_VERSION = "prediction-audit-v1"


def normalize_timestamp(dt_input: Any) -> Optional[str]:
    """Normalizes timestamp to ISO-8601 UTC string with Z suffix."""
    if not dt_input:
        return None
    if isinstance(dt_input, str):
        # Clean string, parse to UTC
        s = dt_input.replace("Z", "+00:00")
        try:
            dt = datetime.fromisoformat(s)
        except ValueError:
            return dt_input
    elif isinstance(dt_input, datetime):
        dt = dt_input
    else:
        return str(dt_input)

    if dt.tzinfo is None:
        dt = dt.replace(tzinfo=timezone.utc)
    else:
        dt = dt.astimezone(timezone.utc)
    return dt.strftime("%Y-%m-%dT%H:%M:%S.%f")[:-3] + "Z"


def normalize_float(val: Any) -> float:
    """Rounds float to 6 decimal places."""
    try:
        f = float(val)
        return round(f, 6)
    except (ValueError, TypeError):
        return 0.0


def compute_complaint_reference(complaint_identifier: Any) -> str:
    """Generates privacy-safe 64-char hex SHA-256 reference for a complaint."""
    cleaned = str(complaint_identifier).strip()
    return hashlib.sha256(f"COMPLAINT_REF:{cleaned}".encode("utf-8")).hexdigest().lower()


def sort_keys_recursively(obj: Any) -> Any:
    """Recursively sorts dictionary keys."""
    if isinstance(obj, dict):
        return {k: sort_keys_recursively(v) for k, v in sorted(obj.items())}
    if isinstance(obj, list):
        return [sort_keys_recursively(elem) for elem in obj]
    return obj


def canonicalize_prediction_audit_payload(prediction_dict: Dict[str, Any]) -> Dict[str, Any]:
    """
    Constructs the deterministic canonical audit payload strictly adhering
    to schema 'prediction-audit-v1'.
    """
    pred_id = int(prediction_dict.get("prediction_id") or 0)
    if pred_id <= 0:
        raise ValueError(f"Invalid prediction_id: {pred_id}")

    comp_ref = prediction_dict.get("complaint_reference_hash")
    if not comp_ref:
        comp_num = prediction_dict.get("complaint_number") or prediction_dict.get("complaint_id")
        if not comp_num:
            raise ValueError("complaint_number or complaint_id is required for complaint reference hash")
        comp_ref = compute_complaint_reference(comp_num)
    comp_ref = str(comp_ref).strip().lower()

    # Top-3 Locations strictly ordered by rank ascending (1, 2, 3)
    raw_locations = prediction_dict.get("top_locations") or prediction_dict.get("ordered_top3") or []
    if len(raw_locations) != 3:
        raise ValueError(f"Expected exactly 3 locations for prediction audit, found {len(raw_locations)}")

    sorted_locs = sorted(raw_locations, key=lambda x: int(x.get("rank", 0)))
    ranks = [int(x.get("rank", 0)) for x in sorted_locs]
    if ranks != [1, 2, 3]:
        raise ValueError(f"top_locations ranks must be strictly [1, 2, 3], found {ranks}")

    ordered_top3 = [
        {
            "cluster_id": int(loc.get("cluster_id")),
            "probability": normalize_float(loc.get("ml_probability") if loc.get("ml_probability") is not None else loc.get("probability", 0.0)),
            "rank": int(loc.get("rank"))
        }
        for loc in sorted_locs
    ]

    raw_time = prediction_dict.get("time_prediction") or prediction_dict.get("time_window") or {}
    time_window = {
        "window_end": normalize_timestamp(raw_time.get("window_end") or prediction_dict.get("predicted_window_end")),
        "window_label": str(raw_time.get("operational_window") or prediction_dict.get("window_label") or "Next 2–4 Hours"),
        "window_start": normalize_timestamp(raw_time.get("window_start") or prediction_dict.get("predicted_window_start"))
    }

    payload = {
        "complaint_reference_hash": comp_ref,
        "location_model_version": str(prediction_dict.get("model_version") or prediction_dict.get("location_model_version") or "cashout-location-xgb-v7-compat"),
        "ordered_top3": ordered_top3,
        "prediction_created_at": normalize_timestamp(prediction_dict.get("created_at") or prediction_dict.get("prediction_created_at") or datetime.utcnow()),
        "prediction_id": pred_id,
        "prediction_mode": str(prediction_dict.get("prediction_mode") or "trained_ml"),
        "time_model_version": str(prediction_dict.get("time_model_version") or raw_time.get("model_version")) if (prediction_dict.get("time_model_version") or raw_time.get("model_version")) else None,
        "time_window": time_window
    }

    return sort_keys_recursively(payload)


def compute_prediction_hash(canonical_payload: Dict[str, Any]) -> str:
    """Computes SHA-256 lowercase 64-char hex string of the canonical JSON."""
    json_bytes = json.dumps(canonical_payload, separators=(',', ':'), ensure_ascii=False).encode('utf-8')
    return hashlib.sha256(json_bytes).hexdigest().lower()


class PredictionAuditClient:
    """Client for anchoring and verifying predictions via Fabric Gateway."""

    def __init__(self, base_url: str = GATEWAY_BASE_URL, timeout_seconds: float = 4.0):
        self.base_url = base_url.rstrip("/")
        self.timeout = timeout_seconds
        self.auth_token = os.environ.get("FABRIC_GATEWAY_TOKEN", "").strip()

    def _get_headers(self) -> Dict[str, str]:
        headers = {"Content-Type": "application/json"}
        if self.auth_token:
            headers["Authorization"] = f"Bearer {self.auth_token}"
            headers["X-API-Key"] = self.auth_token
        return headers

    def anchor_prediction_safe(self, prediction_dict: Dict[str, Any]) -> Dict[str, Any]:
        """
        Non-blocking anchor attempt.
        Never throws an unhandled exception: returns status dictionary.
        """
        try:
            canonical = canonicalize_prediction_audit_payload(prediction_dict)
            pred_hash = compute_prediction_hash(canonical)
        except Exception as e:
            logger.error(f"[PredictionAuditClient] Canonicalization failed for prediction: {e}")
            return {
                "status": "FAILED",
                "error": f"Canonicalization error: {str(e)}",
                "prediction_hash": None,
                "tx_id": None
            }

        payload = {
            "prediction_id": canonical["prediction_id"],
            "complaint_reference_hash": canonical["complaint_reference_hash"],
            "prediction_hash": pred_hash,
            "prediction_mode": canonical["prediction_mode"],
            "location_model_version": canonical["location_model_version"],
            "time_model_version": canonical["time_model_version"],
            "top3_cluster_ids": [loc["cluster_id"] for loc in canonical["ordered_top3"]],
            "prediction_created_at": canonical["prediction_created_at"],
            "schema_version": SCHEMA_VERSION
        }

        if os.environ.get("ENVIRONMENT") == "test" and not os.environ.get("FORCE_FABRIC_GATEWAY"):
            return {
                "status": "PENDING",
                "prediction_hash": pred_hash,
                "error": "Fabric Gateway disabled in test environment",
                "tx_id": None
            }

        try:
            url = f"{self.base_url}/prediction-audit/anchor"
            resp = requests.post(url, json=payload, headers=self._get_headers(), timeout=self.timeout)
            if resp.status_code == 200:
                data = resp.json()
                logger.info(f"[PredictionAuditClient] Prediction #{canonical['prediction_id']} anchored! TxID: {data.get('txId')}")
                return {
                    "status": "ANCHORED",
                    "prediction_hash": pred_hash,
                    "tx_id": data.get("txId"),
                    "schema_version": SCHEMA_VERSION,
                    "anchored_at": datetime.utcnow().isoformat() + "Z"
                }
            else:
                logger.warning(f"[PredictionAuditClient] Gateway returned HTTP {resp.status_code}: {resp.text}")
                return {
                    "status": "ANCHOR_FAILED",
                    "prediction_hash": pred_hash,
                    "error": f"Gateway error HTTP {resp.status_code}",
                    "tx_id": None
                }
        except requests.exceptions.RequestException as exc:
            logger.warning(f"[PredictionAuditClient] Fabric Gateway unreachable: {exc}")
            return {
                "status": "PENDING",
                "prediction_hash": pred_hash,
                "error": f"Fabric Gateway unavailable: {str(exc)}",
                "tx_id": None
            }

    def verify_prediction(self, prediction_dict: Dict[str, Any]) -> Dict[str, Any]:
        """
        Recomputes hash from prediction data and queries Fabric Gateway to verify.
        """
        try:
            canonical = canonicalize_prediction_audit_payload(prediction_dict)
            candidate_hash = compute_prediction_hash(canonical)
            pred_id = canonical["prediction_id"]
        except Exception as e:
            return {
                "verified": False,
                "status": "CANONICALIZATION_ERROR",
                "error": str(e)
            }

        try:
            url = f"{self.base_url}/prediction-audit/{pred_id}/verify-hash"
            resp = requests.post(url, json={"candidate_hash": candidate_hash}, headers=self._get_headers(), timeout=self.timeout)
            if resp.status_code == 200:
                res_data = resp.json()
                return {
                    "verified": res_data.get("verified", False),
                    "status": res_data.get("status"),
                    "prediction_id": pred_id,
                    "computed_hash": candidate_hash,
                    "ledger_hash": res_data.get("ledger_hash"),
                    "fabric_tx_id": res_data.get("fabric_tx_id"),
                    "anchored_at": res_data.get("anchored_at")
                }
            elif resp.status_code == 404:
                return {
                    "verified": False,
                    "status": "ANCHOR_NOT_FOUND",
                    "prediction_id": pred_id,
                    "computed_hash": candidate_hash
                }
            else:
                return {
                    "verified": False,
                    "status": "GATEWAY_ERROR",
                    "error": f"HTTP {resp.status_code}: {resp.text}"
                }
        except requests.exceptions.RequestException as exc:
            return {
                "verified": False,
                "status": "FABRIC_UNAVAILABLE",
                "error": str(exc)
            }


prediction_audit_client = PredictionAuditClient()
