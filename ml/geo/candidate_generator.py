"""
Candidate Location Generator for CyberShield AI
Generates 20–30 plausible candidate location clusters for any complaint based on:
- Beneficiary/mule account geography
- Historical withdrawal hotspots
- Transaction-network geography
- Spatial proximity to victim / last known node
- Regional corridor matching
"""

import math
from typing import List, Dict, Any, Optional

def haversine_km(lat1: float, lon1: float, lat2: float, lon2: float) -> float:
    R = 6371.0
    dlat = math.radians(lat2 - lat1)
    dlon = math.radians(lon2 - lon1)
    a = math.sin(dlat / 2.0)**2 + math.cos(math.radians(lat1)) * math.cos(math.radians(lat2)) * math.sin(dlon / 2.0)**2
    c = 2.0 * math.atan2(math.sqrt(a), math.sqrt(1.0 - a))
    return R * c

import os
import pandas as pd

ZONE_ADJACENCY = {
    "CENTRAL_NEW_DELHI": ["NORTH", "WEST", "SOUTH", "SOUTH_EAST", "EAST"],
    "SOUTH": ["CENTRAL_NEW_DELHI", "SOUTH_EAST", "SOUTH_WEST_DWARKA"],
    "SOUTH_EAST": ["SOUTH", "CENTRAL_NEW_DELHI", "EAST"],
    "WEST": ["CENTRAL_NEW_DELHI", "NORTH_WEST", "SOUTH_WEST_DWARKA"],
    "SOUTH_WEST_DWARKA": ["WEST", "SOUTH"],
    "NORTH": ["CENTRAL_NEW_DELHI", "NORTH_WEST", "NORTH_EAST_SHAHDARA"],
    "NORTH_WEST": ["NORTH", "WEST"],
    "EAST": ["CENTRAL_NEW_DELHI", "SOUTH_EAST", "NORTH_EAST_SHAHDARA"],
    "NORTH_EAST_SHAHDARA": ["EAST", "NORTH"]
}

FRAUD_TYPE_ZONE_AFFINITY = {
    "investment scam": ["CENTRAL_NEW_DELHI", "SOUTH_EAST", "SOUTH"],
    "investment": ["CENTRAL_NEW_DELHI", "SOUTH_EAST", "SOUTH"],
    "phishing": ["NORTH_WEST", "WEST", "EAST"],
    "loan-app scam": ["WEST", "NORTH_WEST", "SOUTH_EAST"],
    "loan app": ["WEST", "NORTH_WEST", "SOUTH_EAST"],
    "fake customer-care scam": ["EAST", "NORTH_EAST_SHAHDARA", "NORTH"],
    "job scam": ["SOUTH_WEST_DWARKA", "WEST", "NORTH_WEST"],
    "part-time job fraud": ["SOUTH_WEST_DWARKA", "WEST", "NORTH_WEST"],
    "impersonation scam": ["CENTRAL_NEW_DELHI", "SOUTH", "NORTH"],
    "digital arrest": ["CENTRAL_NEW_DELHI", "SOUTH", "NORTH"],
    "digital arrest / extortion": ["CENTRAL_NEW_DELHI", "SOUTH", "NORTH"],
    "upi fraud": ["SOUTH", "WEST", "EAST"],
    "upi / qr code fraud": ["SOUTH", "WEST", "EAST"],
    "qr-code scam": ["CENTRAL_NEW_DELHI", "SOUTH_EAST", "NORTH"],
    "remote-access scam": ["WEST", "SOUTH_WEST_DWARKA", "SOUTH_EAST"],
    "account takeover": ["CENTRAL_NEW_DELHI", "NORTH_WEST", "SOUTH"],
    "marketplace scam": ["NORTH", "EAST", "WEST"],
    "e-commerce scam": ["SOUTH_EAST", "EAST", "SOUTH_WEST_DWARKA"]
}

class CandidateLocationGenerator:
    def __init__(self, clusters: Optional[List[Dict[str, Any]]] = None):
        if clusters is None:
            c_path = os.path.join(os.path.dirname(__file__), "..", "data", "clusters.csv")
            if os.path.exists(c_path):
                df = pd.read_csv(c_path)
                clusters = df.to_dict(orient="records")
            else:
                clusters = []
        self.clusters = clusters
        self.cluster_by_id = {c["id"]: c for c in clusters}

    def generate_candidates_for_complaint(
        self,
        complaint: Dict[str, Any],
        beneficiary_mule_cluster_id: Optional[int] = None,
        intermediary_cluster_ids: Optional[List[int]] = None,
        top_k: int = 25,
        transactions: Optional[List[Any]] = None,
        terminal_zone: Optional[str] = None,
        all_tx_zones: Optional[Any] = None
    ) -> List[Dict[str, Any]]:
        """
        Generates top_k candidate clusters without target leakage.
        Incorporates:
        - Complaint origin zone/district and spatial proximity
        - Observed Step-6 account geography (terminal recipient district & intermediate account zones)
        - Historical cluster risk and ATM density
        - Safe fraud type zone affinity priors
        
        Note: beneficiary_mule_cluster_id and intermediary_cluster_ids are retained as
        optional kwargs for backward interface compatibility only, but are ignored to
        prevent outcome leakage.
        """
        v_lat = complaint.get("victim_lat")
        v_lon = complaint.get("victim_lon")
        comp_zone = complaint.get("victim_district") or complaint.get("district")
        ft = str(complaint.get("fraud_type") or "").lower().strip()

        has_valid_coords = (
            v_lat is not None and v_lon is not None and
            not (isinstance(v_lat, float) and math.isnan(v_lat)) and
            not (isinstance(v_lon, float) and math.isnan(v_lon))
        )
        if has_valid_coords:
            try:
                v_lat = float(v_lat)
                v_lon = float(v_lon)
            except (ValueError, TypeError):
                has_valid_coords = False

        # Extract terminal and account zones from transactions if not passed directly
        if terminal_zone is None or all_tx_zones is None:
            resolved_all_zones = set()
            resolved_term_zone = None
            if transactions:
                # Find maximum hop transactions
                max_h = -1
                term_cand_txs = []
                for tx in transactions:
                    hop = getattr(tx, "hop_number", None)
                    if hop is None and isinstance(tx, dict):
                        hop = tx.get("hop_number")
                    hop = int(hop or 1)
                    if hop > max_h:
                        max_h = hop
                        term_cand_txs = [tx]
                    elif hop == max_h:
                        term_cand_txs.append(tx)

                    # Check receiver account district
                    r_acc = getattr(tx, "receiver_account", None)
                    r_dist = getattr(r_acc, "district", None) if r_acc else None
                    if not r_dist and isinstance(tx, dict):
                        r_dist = tx.get("receiver_district") or tx.get("district")
                    if r_dist:
                        resolved_all_zones.add(str(r_dist))

                if term_cand_txs:
                    best_t = max(term_cand_txs, key=lambda x: float(getattr(x, "amount", None) or (x.get("amount") if isinstance(x, dict) else 0.0) or 0.0))
                    r_acc = getattr(best_t, "receiver_account", None)
                    r_dist = getattr(r_acc, "district", None) if r_acc else None
                    if not r_dist and isinstance(best_t, dict):
                        r_dist = best_t.get("receiver_district") or best_t.get("district")
                    if r_dist:
                        resolved_term_zone = str(r_dist)

            if terminal_zone is None:
                terminal_zone = resolved_term_zone
            if all_tx_zones is None:
                all_tx_zones = resolved_all_zones
        elif isinstance(all_tx_zones, (list, tuple)):
            all_tx_zones = set(all_tx_zones)

        # Match fraud type zone affinity
        aff_zones = []
        for k, vz in FRAUD_TYPE_ZONE_AFFINITY.items():
            if k in ft:
                aff_zones = vz
                break

        # Score every cluster in self.clusters without victim-location bias
        scored_candidates = []
        for c in self.clusters:
            c_zone = c.get("district") or c.get("zone")
            c_risk = float(c.get("base_risk", c.get("risk", c.get("risk_score", 0.5))))
            c_atm = float(c.get("atm_density", c.get("atm_count", 15.0)))
            c_lat = float(c.get("lat", c.get("center_lat", 28.6139)))
            c_lon = float(c.get("lon", c.get("center_lon", 77.2090)))

            sc = 0.0
            # 1. Terminal mule zone matching (Causal network evidence)
            if terminal_zone and c_zone == terminal_zone:
                sc += 50.0
            elif terminal_zone and c_zone in ZONE_ADJACENCY.get(terminal_zone, []):
                sc += 25.0

            # 2. Intermediate account zones (Money flow path)
            if all_tx_zones and c_zone in all_tx_zones:
                sc += 15.0

            # 3. Fraud type affinity prior
            if aff_zones and c_zone in aff_zones:
                sc += 20.0

            # 4. Cluster historical risk & ATM infrastructure density
            sc += c_risk * 30.0
            sc += (c_atm / 30.0) * 15.0

            # Distance calculation for informational display only (NO bias score added)
            dist = float("nan")
            if has_valid_coords:
                dist = haversine_km(v_lat, v_lon, c_lat, c_lon)

            cand_obj = {
                "cluster_id": int(c["id"]),
                "id": int(c["id"]),
                "name": str(c.get("name", c.get("cluster_name", ""))),
                "city": str(c.get("city", "Delhi")),
                "state": str(c.get("state", "Delhi")),
                "zone": c_zone,
                "district": c_zone,
                "lat": c_lat,
                "lon": c_lon,
                "latitude": c_lat,
                "longitude": c_lon,
                "atm_density": c_atm,
                "historical_risk": c_risk,
                "base_risk": c_risk,
                "historical_cashout_count": float(c.get("historical_cashout_count", c.get("historical_fraud_count", 230.0))),
                "historical_cashout_amount": float(c.get("historical_cashout_amount", float(c.get("historical_fraud_count", 230.0)) * 50000.0)),
                "distance_from_victim_km": round(dist, 1) if not math.isnan(dist) else float("nan"),
                "candidate_generation_score": round(sc, 2),
                "reasoning": f"Corridor-aware candidate match (score={sc:.1f})"
            }
            scored_candidates.append((sc, cand_obj))

        # Sort by candidate generation score descending
        scored_candidates.sort(key=lambda item: (-item[0], item[1]["id"]))
        if top_k is not None and top_k > 0:
            top_candidates = [item[1] for item in scored_candidates[:top_k]]
        else:
            top_candidates = [item[1] for item in scored_candidates]
        return top_candidates

