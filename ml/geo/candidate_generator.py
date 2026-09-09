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
        top_k: int = 25
    ) -> List[Dict[str, Any]]:
        v_lat = float(complaint.get("victim_lat", 22.75))
        v_lon = float(complaint.get("victim_lon", 75.89))
        v_state = complaint.get("victim_state", "")

        candidates_pool = {}

        # 1. Beneficiary / Mule home cluster (highest operational prior)
        if beneficiary_mule_cluster_id and beneficiary_mule_cluster_id in self.cluster_by_id:
            c = self.cluster_by_id[beneficiary_mule_cluster_id]
            candidates_pool[c["id"]] = {
                "cluster_id": c["id"],
                "name": c["name"],
                "city": c["city"],
                "state": c["state"],
                "lat": c["lat"],
                "lon": c["lon"],
                "atm_density": c.get("atm_density", 15),
                "historical_risk": c.get("base_risk", 0.5),
                "historical_cashout_count": c.get("historical_cashout_count", 500),
                "historical_cashout_amount": c.get("historical_cashout_amount", 25000000.0),
                "reasoning": "Direct beneficiary mule account corridor",
                "is_mule_corridor": 1
            }

        # 1b. Intermediary layering account corridors
        if intermediary_cluster_ids:
            for ic_id in intermediary_cluster_ids:
                if ic_id in self.cluster_by_id and ic_id not in candidates_pool:
                    c = self.cluster_by_id[ic_id]
                    candidates_pool[c["id"]] = {
                        "cluster_id": c["id"],
                        "name": c["name"],
                        "city": c["city"],
                        "state": c["state"],
                        "lat": c["lat"],
                        "lon": c["lon"],
                        "atm_density": c.get("atm_density", 15),
                        "historical_risk": c.get("base_risk", 0.5),
                        "historical_cashout_count": c.get("historical_cashout_count", 500),
                        "historical_cashout_amount": c.get("historical_cashout_amount", 25000000.0),
                        "reasoning": "Intermediary layering transfer corridor",
                        "is_mule_corridor": 0
                    }

        # 2. Distance-based proximity to victim
        distances = []
        for c in self.clusters:
            dist = haversine_km(v_lat, v_lon, c["lat"], c["lon"])
            distances.append((dist, c))

        distances.sort(key=lambda x: x[0])
        # Add 10 closest clusters
        for dist, c in distances[:12]:
            if c["id"] not in candidates_pool:
                candidates_pool[c["id"]] = {
                    "cluster_id": c["id"],
                    "name": c["name"],
                    "city": c["city"],
                    "state": c["state"],
                    "lat": c["lat"],
                    "lon": c["lon"],
                    "atm_density": c.get("atm_density", 15),
                    "historical_risk": c.get("base_risk", 0.5),
                    "historical_cashout_count": c.get("historical_cashout_count", 500),
                    "historical_cashout_amount": c.get("historical_cashout_amount", 25000000.0),
                    "reasoning": f"Proximity to complaint epicenter ({dist:.1f} km)",
                    "is_mule_corridor": 0
                }

        # 3. Top historical cash-out hotspots (state / national level)
        by_risk = sorted(self.clusters, key=lambda x: x.get("base_risk", 0), reverse=True)
        for c in by_risk[:10]:
            if c["id"] not in candidates_pool and len(candidates_pool) < top_k:
                candidates_pool[c["id"]] = {
                    "cluster_id": c["id"],
                    "name": c["name"],
                    "city": c["city"],
                    "state": c["state"],
                    "lat": c["lat"],
                    "lon": c["lon"],
                    "atm_density": c.get("atm_density", 15),
                    "historical_risk": c.get("base_risk", 0.5),
                    "historical_cashout_count": c.get("historical_cashout_count", 500),
                    "historical_cashout_amount": c.get("historical_cashout_amount", 25000000.0),
                    "reasoning": "High-velocity historical cybercrime cash-out hotspot",
                    "is_mule_corridor": 0
                }

        # 4. Same state clusters if still below top_k
        if v_state:
            for c in self.clusters:
                if c["state"] == v_state and c["id"] not in candidates_pool and len(candidates_pool) < top_k:
                    candidates_pool[c["id"]] = {
                        "cluster_id": c["id"],
                        "name": c["name"],
                        "city": c["city"],
                        "state": c["state"],
                        "lat": c["lat"],
                        "lon": c["lon"],
                        "atm_density": c.get("atm_density", 15),
                        "historical_risk": c.get("base_risk", 0.5),
                        "historical_cashout_count": c.get("historical_cashout_count", 500),
                        "historical_cashout_amount": c.get("historical_cashout_amount", 25000000.0),
                        "reasoning": f"Intra-state extraction corridor ({c['city']})",
                        "is_mule_corridor": 0
                    }

        # Calculate distances from victim for all candidates in the pool
        candidate_list = list(candidates_pool.values())
        for c in candidate_list:
            c["distance_from_victim_km"] = round(haversine_km(v_lat, v_lon, c["lat"], c["lon"]), 1)
            c["latitude"] = c["lat"]
            c["longitude"] = c["lon"]

        return candidate_list[:top_k]
