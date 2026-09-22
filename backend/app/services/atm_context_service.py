import math
import logging
from datetime import datetime, timezone
from typing import Optional, List, Dict, Any
from sqlalchemy.orm import Session
from fastapi import HTTPException, status

from backend.app.models.models import (
    Prediction,
    PredictionLocation,
    LocationCluster,
    ATMLocation,
    Complaint,
    Account,
    ComplaintAccount,
    User,
    Organization
)
from backend.app.auth.rbac import verify_complaint_access, complaint_bank_organization_ids

logger = logging.getLogger(__name__)


def haversine_km(lat1: float, lon1: float, lat2: float, lon2: float) -> float:
    """Computes great-circle distance between two GPS coordinates in kilometers."""
    R = 6371.0
    phi1, phi2 = math.radians(lat1), math.radians(lat2)
    dphi = math.radians(lat2 - lat1)
    dlambda = math.radians(lon2 - lon1)

    a = math.sin(dphi / 2.0) ** 2 + math.cos(phi1) * math.cos(phi2) * math.sin(dlambda / 2.0) ** 2
    return 2.0 * R * math.atan2(math.sqrt(a), math.sqrt(1.0 - a))


def _normalized_bank(name: Optional[str]) -> str:
    if not name:
        return ""
    return "".join(c.lower() for c in name if c.isalnum())


class ATMContextService:
    """
    Phase 4: ATM / CSP Contextual Operational Prioritization Service.
    Applies a secondary deterministic contextual intelligence layer inside persisted V8 Top-3 candidate zones.

    Guardrails:
    - ZERO V8 model retraining or inference.
    - ZERO mutation of V8 candidate ranks, probabilities, or LIME explanations.
    - Transparent deterministic contextual scoring (0-100 score, HIGH/MEDIUM/LOW priority bands).
    - Separation of context score from model prediction probability.
    """

    def _score_to_priority_band(self, score: int) -> str:
        """Determines contextual priority band from context score."""
        if score >= 70:
            return "HIGH"
        elif score >= 40:
            return "MEDIUM"
        return "LOW"

    def _fetch_open_street_map_context(self, lat: float, lon: float, radius_km: float = 3.5) -> List[Dict[str, Any]]:
        """Cached OSM contextual data fetcher fallback."""
        return []

    def get_atm_context_for_prediction(
        self,
        db: Session,
        prediction_id: int,
        rank: int,
        user: User
    ) -> Dict[str, Any]:
        # 1. Fetch persisted Prediction & Complaint
        prediction = db.query(Prediction).filter(Prediction.id == prediction_id).first()
        if not prediction:
            raise HTTPException(
                status_code=status.HTTP_404_NOT_FOUND,
                detail=f"Prediction #{prediction_id} not found."
            )

        complaint = db.query(Complaint).filter(Complaint.id == prediction.complaint_id).first()
        if not complaint or not verify_complaint_access(complaint, user, db):
            raise HTTPException(
                status_code=status.HTTP_404_NOT_FOUND,
                detail="Prediction not found or access denied by jurisdiction scope."
            )

        # 2. Fetch specific PredictionLocation by rank (1, 2, or 3)
        pred_loc = (
            db.query(PredictionLocation)
            .filter(
                PredictionLocation.prediction_id == prediction.id,
                PredictionLocation.rank == rank
            )
            .first()
        )
        if not pred_loc:
            # Fallback to rank 1 if requested rank not found
            pred_loc = (
                db.query(PredictionLocation)
                .filter(PredictionLocation.prediction_id == prediction.id)
                .order_by(PredictionLocation.rank.asc())
                .first()
            )
        if not pred_loc:
            raise HTTPException(
                status_code=status.HTTP_404_NOT_FOUND,
                detail=f"No persisted candidate location found for prediction #{prediction_id} rank {rank}."
            )

        target_rank = pred_loc.rank
        target_zone_name = pred_loc.location_name
        target_prob = float(pred_loc.probability or 0.0)

        # 3. Resolve LocationCluster
        cluster = None
        if pred_loc.cluster_id:
            cluster = db.query(LocationCluster).filter(LocationCluster.id == pred_loc.cluster_id).first()
        if not cluster and pred_loc.location_name:
            cluster = db.query(LocationCluster).filter(LocationCluster.cluster_name.ilike(f"%{pred_loc.location_name}%")).first()

        centroid_lat = cluster.center_lat if cluster else (pred_loc.latitude or 28.6315)
        centroid_lon = cluster.center_lon if cluster else (pred_loc.longitude or 77.2167)
        cluster_id = cluster.id if cluster else None

        # 4. Fetch Candidate ATM / CSP points scoped to this candidate cluster
        atms: List[ATMLocation] = []
        if cluster_id:
            atms = db.query(ATMLocation).filter(ATMLocation.cluster_id == cluster_id).all()

        if not atms:
            # Radius search fallback (within 3.5 km of cluster centroid)
            all_atms = db.query(ATMLocation).all()
            atms = [
                a for a in all_atms
                if haversine_km(centroid_lat, centroid_lon, a.latitude, a.longitude) <= 3.5
            ]

        # 5. Extract Beneficiary Account Banks for matching
        beneficiary_banks: Set[str] = set()
        complaint_accounts = (
            db.query(ComplaintAccount)
            .filter(ComplaintAccount.complaint_id == complaint.id)
            .all()
        )
        for ca in complaint_accounts:
            acct = db.query(Account).filter(Account.id == ca.account_id).first()
            if acct and acct.bank_name:
                beneficiary_banks.add(_normalized_bank(acct.bank_name))

        # 6. Score Contextual Cash-Out Points Deterministically
        items = []
        total_cluster_atms = len(atms)

        for atm in atms:
            dist_km = haversine_km(centroid_lat, centroid_lon, atm.latitude, atm.longitude)
            if dist_km > 10.0:
                continue
            atm_bank_norm = _normalized_bank(atm.bank_name)

            bank_match = any(b in atm_bank_norm or atm_bank_norm in b for b in beneficiary_banks) if beneficiary_banks else False

            # Scoring breakdown (Max 100 points):
            # A. Centroid Proximity (0-35 pts)
            proximity_score = max(0.0, 35.0 - (dist_km * 10.0))

            # B. Bank Match (0-25 pts)
            bank_score = 25.0 if bank_match else 0.0

            # C. Local Cash-Out Density (0-20 pts)
            density_score = min(20.0, total_cluster_atms * 3.0)

            # D. Network Endpoint Proximity (0-20 pts)
            endpoint_score = 20.0 if dist_km <= 0.8 else (12.0 if dist_km <= 2.0 else 5.0)

            raw_total = int(round(proximity_score + bank_score + density_score + endpoint_score))
            score = max(0, min(100, raw_total))

            # Priority Bands
            if score >= 70:
                priority_band = "HIGH"
            elif score >= 40:
                priority_band = "MEDIUM"
            else:
                priority_band = "LOW"

            # Reason Breakdown
            reasons = []
            reasons.append(f"{dist_km:.1f} km from candidate zone centroid ({target_zone_name})")

            if bank_match:
                reasons.append(f"Matches beneficiary bank context ({atm.bank_name})")
            else:
                reasons.append(f"Bank affiliation: {atm.bank_name}")

            if total_cluster_atms >= 3:
                reasons.append(f"Located in high-density cash-out zone ({total_cluster_atms} cluster points)")

            if getattr(atm, "cash_available", True):
                reasons.append("Active cash disbursement capability reported")

            item_type = getattr(atm, "location_type", None) or ("CSP" if "CSP" in (atm.atm_code or "") or "CSP" in (atm.address or "") else "ATM")

            items.append({
                "id": atm.id,
                "atm_code": atm.atm_code,
                "name": f"{atm.bank_name} {item_type} — {atm.address}",
                "type": item_type,
                "bank_name": atm.bank_name,
                "bank_code": getattr(atm, "bank_code", None),
                "address": atm.address,
                "city": atm.city,
                "district": atm.district,
                "state": atm.state,
                "latitude": float(atm.latitude),
                "longitude": float(atm.longitude),
                "distance_km": round(dist_km, 2),
                "context_priority_score": score,
                "priority_band": priority_band,
                "bank_match": bank_match,
                "reasons": reasons,
                "source": getattr(atm, "source", "INTERNAL_CONTROLLED_DATA") or "INTERNAL_CONTROLLED_DATA",
                "source_reference": getattr(atm, "source_reference", None),
                "cash_available": getattr(atm, "cash_available", True),
                "risk_rating": getattr(atm, "risk_rating", "MEDIUM") or "MEDIUM"
            })

        # Sort items by context priority score descending
        items.sort(key=lambda x: (x["context_priority_score"], -x["distance_km"]), reverse=True)

        return {
            "prediction_id": prediction.id,
            "complaint_number": complaint.complaint_number,
            "model_version": prediction.model_version or "cashout-location-xgb-v8-debiased",
            "candidate_rank": target_rank,
            "candidate_zone": target_zone_name,
            "candidate_probability": target_prob,
            "context_method": "deterministic_context_v1",
            "disclaimer": (
                "ATM/CSP prioritization is an operational context layer inside the model-predicted zone. "
                "It does not represent a confirmed withdrawal location."
            ),
            "items": items
        }


atm_context_service = ATMContextService()
