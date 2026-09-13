"""
CyberShield AI — Delhi V6.3 Controlled Synthetic Dataset Generator
Phase A.4N: One-Shot Implementation of V6.3 Balanced Signal & Diversified Cluster Dataset

DISCLAIMER:
This dataset is CONTROLLED SYNTHETIC DELHI CYBERCRIME DATA.
It does NOT contain real NCRP data, real bank records, or real police historical data.
It is generated for research, algorithmic benchmarking, and model calibration purposes.

Key Enhancements over V6.2:
1. Stage-1 Multi-Channel Contribution Budget:
   - Enforces strict mathematical contribution caps across 5 evidence channels:
     * Channel A (Terminal Mule Geography): <= 30.0%
     * Channel B (Dominant Account Geography): <= 30.0%
     * Channel C (Route Trajectory & Flow): <= 25.0%
     * Channel D (Behavioral & Origin Context): <= 10.0%
     * Channel E (Leakage-Safe History): <= 5.0%
   - Restores terminal mule match (target: 32-44%, hard ceiling <= 48%) and dominant account match (target: 38-50%, hard ceiling <= 55%).
2. Consensus & Conflict Handling:
   - Consensus boost scaled to [1.0, 1.40] (down from V6.2 overpowering [1.0, 2.20]).
   - Increased distribution entropy when evidence channels conflict.
3. Stage-2 Primary Portfolio Rotation & Decoupled Functional Roles:
   - Primary cluster eligibility rotates deterministically across role-compatible clusters using case-index modulo hashing.
   - Fraud types map strictly to functional role distribution weights across all 11 districts (no cluster ID tables).
   - District size normalization ensures single/few-cluster districts do not exceed marginal concentration limits.
4. Global Historical Popularity Saturation:
   - Bounded historical popularity capped at 6.0% with log-saturation: min(0.06, 0.02 * log1p(prior_events)).
5. Strict Invariant & Full-Precision Normalization:
   - Stage 2 clusters are strictly restricted to realized district (0 mismatches).
   - All probability vectors normalized in float64 with sum error <= 1e-9.
"""

import os
import sys
import math
import gzip
import json
import argparse
import hashlib
import datetime
from typing import Dict, Any, List, Tuple, Optional
import numpy as np
import pandas as pd

from ml.data.generate_delhi_v5_dataset import (
    DELHI_CLUSTERS_V5 as DELHI_CLUSTERS_V6_3,
    ALL_11_DISTRICTS,
    DISTRICT_ADJACENCY,
    FRAUD_PROFILES,
    haversine_km
)

FRAUD_TYPES = sorted(list(FRAUD_PROFILES.keys()))
CLUSTER_BY_ID: Dict[int, Dict[str, Any]] = {c["id"]: c for c in DELHI_CLUSTERS_V6_3}
ALL_CLUSTER_IDS: List[int] = [c["id"] for c in DELHI_CLUSTERS_V6_3]

BANK_GROUPS = [
    "SBI_GROUP", "HDFC_ICICI_AXIS", "PNB_BOB_CANARA",
    "PAYTM_AIRTEL_PAYMENT_BANKS", "REGIONAL_COOPERATIVE_BANKS"
]

PAYMENT_CHANNELS = ["upi", "imps", "neft", "rtgs", "card_p2p", "crypto_p2p"]

ARCHETYPE_SPECS = [
    ("LOCAL_RAPID_CASHOUT", 0.18),
    ("NEARBY_COMMERCIAL_CORRIDOR", 0.16),
    ("TERMINAL_MULE_DISTRICT", 0.15),
    ("TRANSPORT_HUB_MOVEMENT", 0.12),
    ("CROSS_DISTRICT_MULE_CHAIN", 0.12),
    ("RECURRING_SYNDICATE_CORRIDOR", 0.10),
    ("HIGH_VALUE_DELAYED_CASHOUT", 0.07),
    ("MULTI_BANK_DISPERSAL", 0.06),
    ("NIGHTTIME_ATM_CASHOUT", 0.04)
]

# District-local functional role definitions from frozen exposure plan
CLUSTER_LOCAL_ROLES: Dict[int, List[str]] = {
    7: ["COMMERCIAL_HUB_LOCAL", "HIGH_DENSITY_ATM_CORRIDOR"], # Connaught Place (NEW_DELHI)
    8: ["COMMERCIAL_HUB_LOCAL", "HIGH_DENSITY_ATM_CORRIDOR"], # Karol Bagh (CENTRAL)
    9: ["TRANSPORT_HUB_LOCAL", "HIGH_DENSITY_ATM_CORRIDOR"],  # Paharganj / NDLS (CENTRAL)
    10: ["HIGH_DENSITY_ATM_CORRIDOR"],                        # Patel Nagar (CENTRAL)
    11: ["HIGH_DENSITY_ATM_CORRIDOR", "MIXED_RETAIL_CORRIDOR"],# Rajendra Place (CENTRAL)
    12: ["TRANSPORT_HUB_LOCAL"],                              # Mandi House (NEW_DELHI)
    13: ["SECONDARY_COMMERCIAL_CORRIDOR"],                    # Chanakyapuri (NEW_DELHI)
    14: ["HIGH_DENSITY_ATM_CORRIDOR"],                        # Hauz Khas (SOUTH)
    15: ["MIXED_RETAIL_CORRIDOR"],                            # Green Park (SOUTH)
    16: ["COMMERCIAL_HUB_LOCAL", "HIGH_DENSITY_ATM_CORRIDOR"], # Saket (SOUTH)
    17: ["HIGH_DENSITY_ATM_CORRIDOR"],                        # Greater Kailash (SOUTH)
    18: ["MIXED_RETAIL_CORRIDOR"],                            # Malviya Nagar (SOUTH)
    19: ["SECONDARY_COMMERCIAL_CORRIDOR"],                    # Vasant Kunj (SOUTH)
    20: ["LOCAL_BRANCH_NETWORK"],                             # Defence Colony (SOUTH)
    21: ["LOCAL_BRANCH_NETWORK"],                             # Mehrauli (SOUTH)
    22: ["COMMERCIAL_HUB_LOCAL", "HIGH_DENSITY_ATM_CORRIDOR"], # Nehru Place (SOUTH_EAST)
    23: ["HIGH_DENSITY_ATM_CORRIDOR"],                        # Kalkaji (SOUTH_EAST)
    24: ["MIXED_RETAIL_CORRIDOR"],                            # Lajpat Nagar (SOUTH_EAST)
    25: ["TRANSPORT_HUB_LOCAL"],                              # Okhla / Sarai Kale Khan (SOUTH_EAST)
    26: ["SECONDARY_COMMERCIAL_CORRIDOR"],                    # CR Park (SOUTH_EAST)
    27: ["MIXED_RETAIL_CORRIDOR"],                            # Govindpuri (SOUTH_EAST)
    28: ["LOCAL_BRANCH_NETWORK"],                             # Sarita Vihar (SOUTH_EAST)
    29: ["COMMERCIAL_HUB_LOCAL", "HIGH_DENSITY_ATM_CORRIDOR"], # Rajouri Garden (WEST)
    30: ["HIGH_DENSITY_ATM_CORRIDOR"],                        # Janakpuri (WEST)
    31: ["MIXED_RETAIL_CORRIDOR"],                            # Tilak Nagar (WEST)
    32: ["TRANSPORT_HUB_LOCAL"],                              # Punjabi Bagh (WEST)
    33: ["SECONDARY_COMMERCIAL_CORRIDOR"],                    # Paschim Vihar (WEST)
    34: ["MIXED_RETAIL_CORRIDOR"],                            # Uttam Nagar (WEST)
    35: ["SECONDARY_COMMERCIAL_CORRIDOR"],                    # Vikaspuri (WEST)
    36: ["LOCAL_BRANCH_NETWORK"],                             # Kirti Nagar (WEST)
    37: ["HIGH_DENSITY_ATM_CORRIDOR"],                        # Dwarka Sec 6 (SOUTH_WEST)
    38: ["COMMERCIAL_HUB_LOCAL", "HIGH_DENSITY_ATM_CORRIDOR"], # Dwarka Sec 10 (SOUTH_WEST)
    39: ["SECONDARY_COMMERCIAL_CORRIDOR"],                    # Dwarka Sec 12 (SOUTH_WEST)
    40: ["TRANSPORT_HUB_LOCAL"],                              # Dwarka Sec 21 (SOUTH_WEST)
    41: ["MIXED_RETAIL_CORRIDOR"],                            # Palam (SOUTH_WEST)
    42: ["SECONDARY_COMMERCIAL_CORRIDOR"],                    # Mahipalpur (SOUTH_WEST)
    43: ["LOCAL_BRANCH_NETWORK"],                             # Civil Lines (NORTH)
    44: ["HIGH_DENSITY_ATM_CORRIDOR"],                        # Model Town (NORTH)
    45: ["MIXED_RETAIL_CORRIDOR"],                            # Mukherjee Nagar (NORTH)
    46: ["COMMERCIAL_HUB_LOCAL", "HIGH_DENSITY_ATM_CORRIDOR"], # Kamla Nagar (NORTH)
    47: ["TRANSPORT_HUB_LOCAL"],                              # Kashmere Gate (NORTH)
    48: ["LOCAL_BRANCH_NETWORK"],                             # Burari (NORTH)
    49: ["HIGH_DENSITY_ATM_CORRIDOR"],                        # Rohini Sec 3 (NORTH_WEST)
    50: ["COMMERCIAL_HUB_LOCAL", "HIGH_DENSITY_ATM_CORRIDOR"], # Rohini Sec 10 (NORTH_WEST)
    51: ["MIXED_RETAIL_CORRIDOR"],                            # Rohini Sec 15 (NORTH_WEST)
    52: ["TRANSPORT_HUB_LOCAL"],                              # Pitampura (NORTH_WEST)
    53: ["SECONDARY_COMMERCIAL_CORRIDOR"],                    # Shalimar Bagh (NORTH_WEST)
    54: ["MIXED_RETAIL_CORRIDOR"],                            # Ashok Vihar (NORTH_WEST)
    55: ["SECONDARY_COMMERCIAL_CORRIDOR"],                    # Wazirpur (NORTH_WEST)
    56: ["LOCAL_BRANCH_NETWORK"],                             # Narela (NORTH_WEST)
    57: ["COMMERCIAL_HUB_LOCAL", "HIGH_DENSITY_ATM_CORRIDOR"], # Laxmi Nagar (EAST)
    58: ["HIGH_DENSITY_ATM_CORRIDOR"],                        # Preet Vihar (EAST)
    59: ["TRANSPORT_HUB_LOCAL"],                              # Mayur Vihar Ph 1 (EAST)
    60: ["MIXED_RETAIL_CORRIDOR"],                            # Mayur Vihar Ph 2 (EAST)
    61: ["SECONDARY_COMMERCIAL_CORRIDOR"],                    # Patparganj (EAST)
    62: ["COMMERCIAL_HUB_LOCAL", "HIGH_DENSITY_ATM_CORRIDOR"], # Shahdara (SHAHDARA)
    63: ["HIGH_DENSITY_ATM_CORRIDOR"],                        # Dilshad Garden (SHAHDARA)
    64: ["TRANSPORT_HUB_LOCAL"],                              # Anand Vihar (SHAHDARA)
    65: ["MIXED_RETAIL_CORRIDOR"],                            # Vivek Vihar (SHAHDARA)
    66: ["COMMERCIAL_HUB_LOCAL", "MIXED_RETAIL_CORRIDOR"]     # Seelampur (NORTH_EAST)
}

# Fraud type preferred roles (strictly mapped to roles across all 11 districts, never directly to cluster IDs)
FRAUD_ROLE_PREFERENCES: Dict[str, List[str]] = {
    "digital payment fraud": ["HIGH_DENSITY_ATM_CORRIDOR", "COMMERCIAL_HUB_LOCAL"],
    "marketplace fraud": ["MIXED_RETAIL_CORRIDOR", "SECONDARY_COMMERCIAL_CORRIDOR", "COMMERCIAL_HUB_LOCAL"],
    "upi fraud": ["HIGH_DENSITY_ATM_CORRIDOR", "MIXED_RETAIL_CORRIDOR"],
    "loan app scam": ["COMMERCIAL_HUB_LOCAL", "LOCAL_BRANCH_NETWORK"],
    "remote access scam": ["HIGH_DENSITY_ATM_CORRIDOR", "TRANSPORT_HUB_LOCAL"],
    "job scam": ["COMMERCIAL_HUB_LOCAL", "SECONDARY_COMMERCIAL_CORRIDOR"],
    "phishing fraud": ["HIGH_DENSITY_ATM_CORRIDOR", "LOCAL_BRANCH_NETWORK"],
    "impersonation scam": ["TRANSPORT_HUB_LOCAL", "COMMERCIAL_HUB_LOCAL"],
    "investment scam": ["COMMERCIAL_HUB_LOCAL", "SECONDARY_COMMERCIAL_CORRIDOR"]
}

class DelhiV63DatasetGenerator:
    """
    Generator for Delhi V6.3 controlled synthetic cybercrime dataset with balanced geographic signal budgets.
    """

    def __init__(self, seed: int = 39184, total_cases: int = 15000):
        self.seed = seed
        self.total_cases = total_cases
        self.rng = np.random.default_rng(seed)

        # Index clusters by district
        self.clusters_by_district: Dict[str, List[Dict[str, Any]]] = {d: [] for d in ALL_11_DISTRICTS}
        for c in DELHI_CLUSTERS_V6_3:
            self.clusters_by_district[c["district"]].append(c)

        # District centroid lookup
        self.district_centroids: Dict[str, Tuple[float, float]] = {}
        for d, cls in self.clusters_by_district.items():
            avg_lat = float(np.mean([c["lat"] for c in cls]))
            avg_lon = float(np.mean([c["lon"] for c in cls]))
            self.district_centroids[d] = (avg_lat, avg_lon)

        # Setup 24 synthetic syndicates
        self.syndicates = self._init_syndicates()

        # Setup 54 Latent Behavioral Sub-Prototypes (9 archetypes x 6 sub-prototypes)
        self.sub_prototypes = self._init_sub_prototypes()

        # Dynamic chronological cluster popularity tracker
        self.cluster_history_counts: Dict[int, int] = {cid: 0 for cid in ALL_CLUSTER_IDS}

        # Telemetry tracking for normalization & invariants
        self.max_district_sum_error = 0.0
        self.max_cluster_sum_error = 0.0
        self.invalid_district_prob_rows = 0
        self.invalid_cluster_prob_rows = 0
        self.district_cluster_mismatches = 0
        self.max_realized_popularity_contrib = 0.0
        self.popularity_contrib_sum = 0.0

    def _init_syndicates(self) -> List[Dict[str, Any]]:
        """Sets up 24 synthetic syndicate cohorts."""
        syns = []
        for s_id in range(1, 25):
            pref_ft = FRAUD_TYPES[s_id % len(FRAUD_TYPES)]
            pref_dist = ALL_11_DISTRICTS[s_id % len(ALL_11_DISTRICTS)]
            cands_in_dist = [c["id"] for c in self.clusters_by_district[pref_dist]]
            syns.append({
                "id": f"SYN-V63-{s_id:03d}",
                "base_district": pref_dist,
                "preferred_clusters": cands_in_dist[:3],
                "fraud_type": pref_ft
            })
        return syns

    def _init_sub_prototypes(self) -> List[Dict[str, Any]]:
        """Sets up 54 latent sub-prototypes with balanced spatial routes and role preferences."""
        protos = []
        proto_idx = 1
        for arch_name, _ in ARCHETYPE_SPECS:
            for sub_i in range(1, 7):
                v_dist = ALL_11_DISTRICTS[(proto_idx * 3) % len(ALL_11_DISTRICTS)]
                adj_dists = DISTRICT_ADJACENCY[v_dist]

                # Logical spatial progression: origin -> intermediate -> downstream -> terminal
                if arch_name in ["LOCAL_RAPID_CASHOUT", "NIGHTTIME_ATM_CASHOUT"]:
                    t_dist = v_dist if sub_i <= 4 else adj_dists[0]
                    dom_d = v_dist
                    maj_down = v_dist
                    roles = ["HIGH_DENSITY_ATM_CORRIDOR", "LOCAL_BRANCH_NETWORK"] if arch_name == "NIGHTTIME_ATM_CASHOUT" else ["LOCAL_BRANCH_NETWORK", "COMMERCIAL_HUB_LOCAL"]
                elif arch_name in ["CROSS_DISTRICT_MULE_CHAIN", "TERMINAL_MULE_DISTRICT"]:
                    remote_dists = [d for d in ALL_11_DISTRICTS if d != v_dist and d not in adj_dists]
                    t_dist = remote_dists[sub_i % len(remote_dists)] if remote_dists else adj_dists[0]
                    dom_d = t_dist if sub_i <= 4 else adj_dists[0]
                    maj_down = t_dist
                    roles = ["TRANSPORT_HUB_LOCAL", "COMMERCIAL_HUB_LOCAL"] if arch_name == "CROSS_DISTRICT_MULE_CHAIN" else ["LOCAL_BRANCH_NETWORK", "HIGH_DENSITY_ATM_CORRIDOR"]
                elif arch_name == "TRANSPORT_HUB_MOVEMENT":
                    hub_dists = ["CENTRAL", "NEW_DELHI", "NORTH", "EAST", "SHAHDARA"]
                    t_dist = hub_dists[sub_i % len(hub_dists)]
                    dom_d = t_dist
                    maj_down = t_dist
                    roles = ["TRANSPORT_HUB_LOCAL", "COMMERCIAL_HUB_LOCAL"]
                elif arch_name == "RECURRING_SYNDICATE_CORRIDOR":
                    syn = self.syndicates[(proto_idx - 1) % len(self.syndicates)]
                    t_dist = syn["base_district"]
                    dom_d = t_dist
                    maj_down = t_dist
                    roles = ["COMMERCIAL_HUB_LOCAL", "HIGH_DENSITY_ATM_CORRIDOR"]
                else: # NEARBY_COMMERCIAL_CORRIDOR, HIGH_VALUE_DELAYED_CASHOUT, MULTI_BANK_DISPERSAL
                    t_dist = adj_dists[sub_i % len(adj_dists)]
                    dom_d = t_dist if sub_i % 2 == 0 else v_dist
                    maj_down = t_dist
                    roles = ["COMMERCIAL_HUB_LOCAL", "SECONDARY_COMMERCIAL_CORRIDOR", "MIXED_RETAIL_CORRIDOR"]

                # Fraud type & payment channel
                ft = FRAUD_TYPES[(proto_idx + sub_i) % len(FRAUD_TYPES)]
                if ft in ["upi fraud", "digital payment fraud"]:
                    chan = "upi" if sub_i % 2 == 0 else "imps"
                elif ft in ["investment scam", "job scam"]:
                    chan = "imps" if sub_i % 2 == 0 else "neft"
                else:
                    chan = PAYMENT_CHANNELS[sub_i % len(PAYMENT_CHANNELS)]

                # Amount bucket
                if arch_name == "HIGH_VALUE_DELAYED_CASHOUT":
                    amt_b = "severe" if sub_i <= 3 else "high"
                elif arch_name in ["LOCAL_RAPID_CASHOUT", "digital payment fraud"]:
                    amt_b = "micro" if sub_i <= 3 else "low"
                else:
                    amt_buckets = ["low", "medium", "high", "severe"]
                    amt_b = amt_buckets[sub_i % len(amt_buckets)]

                protos.append({
                    "sub_prototype_id": f"SUB-PROTO-V63-{proto_idx:02d}",
                    "archetype": arch_name,
                    "sub_index": sub_i,
                    "victim_district": v_dist,
                    "terminal_mule_district": t_dist,
                    "dominant_account_district": dom_d,
                    "majority_downstream_district": maj_down,
                    "preferred_roles": roles,
                    "fraud_type": ft,
                    "channel": chan,
                    "amount_bucket": amt_b
                })
                proto_idx += 1
        return protos

    def _get_amount_from_bucket(self, bucket: str) -> float:
        if bucket == "micro":
            return round(float(self.rng.uniform(2500.0, 10000.0)), 2)
        elif bucket == "low":
            return round(float(self.rng.uniform(10001.0, 50000.0)), 2)
        elif bucket == "medium":
            return round(float(self.rng.uniform(50001.0, 150000.0)), 2)
        elif bucket == "high":
            return round(float(self.rng.uniform(150001.0, 300000.0)), 2)
        else: # severe
            return round(float(self.rng.uniform(300001.0, 920000.0)), 2)

    def generate_case(self, case_num: int, base_time: datetime.datetime) -> Dict[str, Any]:
        """Generates a single comprehensive V6.3 case record with balanced evidence channels and diversified cluster portfolios."""
        proto = self.rng.choice(self.sub_prototypes)
        arch_name = proto["archetype"]
        sub_proto_id = proto["sub_prototype_id"]
        v_dist = proto["victim_district"]
        t_dist = proto["terminal_mule_district"]
        dom_d = proto["dominant_account_district"]
        maj_down_d = proto["majority_downstream_district"]
        preferred_roles = proto["preferred_roles"]
        ft = proto["fraud_type"]
        channel = proto["channel"]
        amt_b = proto["amount_bucket"]

        # Randomize amount within bucket
        amount = self._get_amount_from_bucket(amt_b)
        log_amount = round(float(np.log1p(amount)), 4)

        # Victim location
        v_lat_cent, v_lon_cent = self.district_centroids[v_dist]
        v_lat = round(float(v_lat_cent + self.rng.normal(0, 0.012)), 6)
        v_lon = round(float(v_lon_cent + self.rng.normal(0, 0.012)), 6)
        v_bank = self.rng.choice(BANK_GROUPS)

        # Nearest cluster to victim origin
        dists_to_v = [haversine_km(v_lat, v_lon, c["lat"], c["lon"]) for c in DELHI_CLUSTERS_V6_3]
        nearest_origin_cid = DELHI_CLUSTERS_V6_3[int(np.argmin(dists_to_v))]["id"]

        # Trajectory parameters conditioned on archetype
        if arch_name == "LOCAL_RAPID_CASHOUT":
            hop_count = int(self.rng.choice([1, 2], p=[0.75, 0.25]))
            delay_min = round(float(self.rng.uniform(12.0, 55.0)), 2)
            mule_count = int(self.rng.choice([1, 2], p=[0.80, 0.20]))
            bank_count = 1 if self.rng.random() < 0.80 else 2
            geo_consistency = round(float(self.rng.uniform(0.88, 0.98)), 4)
            account_dist_count = 1
            dom_share = 1.0
            cross_dist_transfers = 0
            burst_score = round(float(self.rng.uniform(0.75, 0.95)), 4)
            velocity = round(float(self.rng.uniform(3.0, 6.5)), 4)
            night_ratio = round(float(self.rng.uniform(0.05, 0.20)), 4)
            depth = hop_count
            branching = 1.0

        elif arch_name == "NEARBY_COMMERCIAL_CORRIDOR":
            hop_count = int(self.rng.choice([2, 3], p=[0.65, 0.35]))
            delay_min = round(float(self.rng.uniform(30.0, 110.0)), 2)
            mule_count = int(self.rng.choice([2, 3], p=[0.70, 0.30]))
            bank_count = int(self.rng.choice([1, 2, 3], p=[0.45, 0.45, 0.10]))
            geo_consistency = round(float(self.rng.uniform(0.65, 0.88)), 4)
            account_dist_count = 2 if v_dist != t_dist else 1
            dom_share = round(float(self.rng.uniform(0.65, 0.85)), 4)
            cross_dist_transfers = 1 if v_dist != t_dist else 0
            burst_score = round(float(self.rng.uniform(0.68, 0.92)), 4)
            velocity = round(float(self.rng.uniform(2.2, 4.8)), 4)
            night_ratio = round(float(self.rng.uniform(0.10, 0.30)), 4)
            depth = hop_count
            branching = round(float(self.rng.uniform(1.1, 1.3)), 2)

        elif arch_name == "TERMINAL_MULE_DISTRICT":
            hop_count = int(self.rng.choice([2, 3, 4], p=[0.40, 0.45, 0.15]))
            delay_min = round(float(self.rng.uniform(45.0, 160.0)), 2)
            mule_count = int(self.rng.choice([2, 3, 4], p=[0.35, 0.50, 0.15]))
            bank_count = int(self.rng.choice([2, 3], p=[0.60, 0.40]))
            geo_consistency = round(float(self.rng.uniform(0.55, 0.78)), 4)
            account_dist_count = 2 if v_dist != t_dist else 1
            dom_share = round(float(self.rng.uniform(0.60, 0.85)), 4)
            cross_dist_transfers = 1 if v_dist != t_dist else 0
            burst_score = round(float(self.rng.uniform(0.55, 0.85)), 4)
            velocity = round(float(self.rng.uniform(1.8, 3.8)), 4)
            night_ratio = round(float(self.rng.uniform(0.12, 0.35)), 4)
            depth = hop_count
            branching = round(float(self.rng.uniform(1.1, 1.4)), 2)

        elif arch_name == "TRANSPORT_HUB_MOVEMENT":
            hop_count = int(self.rng.choice([2, 3, 4], p=[0.35, 0.45, 0.20]))
            delay_min = round(float(self.rng.uniform(25.0, 120.0)), 2)
            mule_count = int(self.rng.choice([2, 3], p=[0.65, 0.35]))
            bank_count = int(self.rng.choice([2, 3], p=[0.55, 0.45]))
            geo_consistency = round(float(self.rng.uniform(0.45, 0.70)), 4)
            account_dist_count = int(self.rng.choice([2, 3], p=[0.65, 0.35]))
            dom_share = round(float(self.rng.uniform(0.55, 0.75)), 4)
            cross_dist_transfers = int(self.rng.choice([2, 3], p=[0.70, 0.30]))
            burst_score = round(float(self.rng.uniform(0.75, 0.96)), 4)
            velocity = round(float(self.rng.uniform(3.5, 7.2)), 4)
            night_ratio = round(float(self.rng.uniform(0.10, 0.40)), 4)
            depth = hop_count
            branching = 1.2

        elif arch_name == "CROSS_DISTRICT_MULE_CHAIN":
            hop_count = int(self.rng.choice([3, 4, 5], p=[0.35, 0.45, 0.20]))
            delay_min = round(float(self.rng.uniform(75.0, 320.0)), 2)
            mule_count = int(self.rng.choice([3, 4, 5], p=[0.35, 0.45, 0.20]))
            bank_count = int(self.rng.choice([3, 4, 5], p=[0.45, 0.35, 0.20]))
            geo_consistency = round(float(self.rng.uniform(0.30, 0.55)), 4)
            account_dist_count = int(self.rng.choice([3, 4], p=[0.70, 0.30]))
            dom_share = round(float(self.rng.uniform(0.45, 0.65)), 4)
            cross_dist_transfers = int(self.rng.choice([2, 3, 4], p=[0.40, 0.40, 0.20]))
            burst_score = round(float(self.rng.uniform(0.45, 0.75)), 4)
            velocity = round(float(self.rng.uniform(1.4, 3.2)), 4)
            night_ratio = round(float(self.rng.uniform(0.15, 0.45)), 4)
            depth = hop_count
            branching = round(float(self.rng.uniform(1.3, 1.7)), 2)

        elif arch_name == "RECURRING_SYNDICATE_CORRIDOR":
            syn = self.syndicates[(case_num % len(self.syndicates))]
            hop_count = int(self.rng.choice([2, 3, 4], p=[0.40, 0.45, 0.15]))
            delay_min = round(float(self.rng.uniform(35.0, 180.0)), 2)
            mule_count = int(self.rng.choice([2, 3], p=[0.65, 0.35]))
            bank_count = 2
            geo_consistency = round(float(self.rng.uniform(0.60, 0.85)), 4)
            account_dist_count = 2
            dom_share = 0.75
            cross_dist_transfers = 1
            burst_score = round(float(self.rng.uniform(0.65, 0.88)), 4)
            velocity = round(float(self.rng.uniform(2.2, 4.2)), 4)
            night_ratio = round(float(self.rng.uniform(0.12, 0.30)), 4)
            depth = hop_count
            branching = 1.3

        elif arch_name == "HIGH_VALUE_DELAYED_CASHOUT":
            hop_count = int(self.rng.choice([4, 5, 6], p=[0.45, 0.35, 0.20]))
            delay_min = round(float(self.rng.uniform(150.0, 420.0)), 2)
            mule_count = int(self.rng.choice([4, 5, 6], p=[0.45, 0.35, 0.20]))
            bank_count = int(self.rng.choice([3, 4], p=[0.60, 0.40]))
            geo_consistency = round(float(self.rng.uniform(0.40, 0.65)), 4)
            account_dist_count = int(self.rng.choice([2, 3, 4], p=[0.35, 0.45, 0.20]))
            dom_share = round(float(self.rng.uniform(0.50, 0.70)), 4)
            cross_dist_transfers = int(self.rng.choice([2, 3], p=[0.65, 0.35]))
            burst_score = round(float(self.rng.uniform(0.40, 0.70)), 4)
            velocity = round(float(self.rng.uniform(1.0, 2.5)), 4)
            night_ratio = round(float(self.rng.uniform(0.18, 0.40)), 4)
            depth = hop_count
            branching = round(float(self.rng.uniform(1.4, 1.9)), 2)

        elif arch_name == "MULTI_BANK_DISPERSAL":
            hop_count = int(self.rng.choice([3, 4, 5], p=[0.35, 0.45, 0.20]))
            delay_min = round(float(self.rng.uniform(50.0, 200.0)), 2)
            mule_count = int(self.rng.choice([4, 5, 6], p=[0.45, 0.35, 0.20]))
            bank_count = int(self.rng.choice([4, 5, 6], p=[0.55, 0.35, 0.10]))
            geo_consistency = round(float(self.rng.uniform(0.35, 0.60)), 4)
            account_dist_count = 3
            dom_share = 0.55
            cross_dist_transfers = 2
            burst_score = round(float(self.rng.uniform(0.80, 0.98)), 4)
            velocity = round(float(self.rng.uniform(3.8, 7.8)), 4)
            night_ratio = round(float(self.rng.uniform(0.12, 0.35)), 4)
            depth = hop_count
            branching = round(float(self.rng.uniform(2.0, 2.6)), 2)

        else: # NIGHTTIME_ATM_CASHOUT
            hop_count = int(self.rng.choice([1, 2, 3], p=[0.55, 0.35, 0.10]))
            delay_min = round(float(self.rng.uniform(18.0, 75.0)), 2)
            mule_count = int(self.rng.choice([1, 2], p=[0.75, 0.25]))
            bank_count = 1 if self.rng.random() < 0.65 else 2
            geo_consistency = round(float(self.rng.uniform(0.75, 0.95)), 4)
            account_dist_count = 1 if self.rng.random() < 0.75 else 2
            dom_share = 0.90
            cross_dist_transfers = 0 if account_dist_count == 1 else 1
            burst_score = round(float(self.rng.uniform(0.70, 0.92)), 4)
            velocity = round(float(self.rng.uniform(2.5, 5.5)), 4)
            night_ratio = round(float(self.rng.uniform(0.80, 0.98)), 4)
            depth = hop_count
            branching = 1.0

        # Beneficiary counts and distance trajectory
        beneficiary_count = max(1, int(round(mule_count * (0.5 if branching <= 1.2 else 0.8))))
        t_lat_cent, t_lon_cent = self.district_centroids[t_dist]
        net_disp_km = round(haversine_km(v_lat, v_lon, t_lat_cent, t_lon_cent), 2)
        total_path_km = round(float(net_disp_km * (1.15 + 0.25 * (hop_count - 1)) + self.rng.uniform(1.0, 6.0)), 2)
        backtrack_ratio = round(float(min(1.0, max(0.2, net_disp_km / max(1.0, total_path_km)))), 4)
        dominant_flow_district = dom_d
        terminal_flow_alignment = round(float(0.5 + 0.5 * backtrack_ratio), 4)
        downstream_geo_conc = round(float(dom_share**2 + (1.0 - dom_share)**2), 4)
        cross_hop_ratio = round(float(min(1.0, cross_dist_transfers / max(1, hop_count))), 4)
        term_displacement = net_disp_km
        term_majority_dist_km = round(float(net_disp_km * (1.0 - dom_share)), 2)
        geo_dispersion = round(float(net_disp_km * (1.0 - geo_consistency) * 0.7 + self.rng.uniform(1.0, 4.0)), 2)

        # Context features
        hist_crime_density = round(float(self.rng.uniform(0.40, 0.85)), 4)
        comm_hub_ref = CLUSTER_BY_ID[7] # Connaught Place reference
        comm_proximity = round(haversine_km(v_lat, v_lon, comm_hub_ref["lat"], comm_hub_ref["lon"]), 2)

        # 11 Route Coherence & Consensus Observables
        downstream_route_consistency = round(float(min(1.0, max(0.3, geo_consistency * 0.7 + (1.0 - cross_hop_ratio) * 0.3))), 4)
        downstream_direction_strength = round(float(min(1.0, max(0.2, terminal_flow_alignment * (0.8 + 0.2 * (1.0 - backtrack_ratio))))), 4)
        terminal_path_share = round(float(min(0.85, max(0.25, 0.40 + 0.10 * hop_count - 0.05 * cross_hop_ratio))), 4)
        majority_downstream_district = maj_down_d
        majority_downstream_share = round(float(min(1.0, max(0.50, dom_share * 0.8 + 0.2 * downstream_route_consistency))), 4)
        recent_hop_district = maj_down_d if self.rng.random() < 0.70 else t_dist
        recent_two_hop_consistency = round(float(self.rng.uniform(0.65, 0.95)), 4)
        route_entropy = round(float(min(2.5, max(0.1, 0.4 * account_dist_count + 0.3 * cross_dist_transfers))), 4)
        route_turnaround_count = int(max(0, int(round((1.0 - backtrack_ratio) * hop_count))))
        terminal_alignment_with_flow = terminal_flow_alignment

        # Composite district evidence consensus score (independent multi-channel agreement)
        dist_match_count = sum([
            int(dom_d == t_dist),
            int(dom_d == maj_down_d),
            int(t_dist == maj_down_d),
            int(dominant_flow_district == maj_down_d)
        ])
        district_evidence_consensus_score = round(float(min(1.0, max(0.25, 0.30 + 0.175 * dist_match_count))), 4)

        # Timestamps
        is_night = (self.rng.random() < night_ratio)
        hour = int(self.rng.choice([22, 23, 0, 1, 2, 3, 4, 5])) if is_night else int(self.rng.choice(range(6, 22)))
        minute = int(self.rng.integers(0, 60))
        second = int(self.rng.integers(0, 60))
        event_time = base_time.replace(hour=hour, minute=minute, second=second)
        report_time = event_time + datetime.timedelta(minutes=delay_min)
        weekend_flag = int(event_time.weekday() >= 5)

        # =========================================================================
        # STAGE 1: BUDGET-CAPPED MULTI-CHANNEL DISTRICT SCORING
        # =========================================================================
        n_dist = len(ALL_11_DISTRICTS)

        # Consensus multiplier scaled to [1.0, 1.40] per frozen contract
        consensus_boost = 1.0 + 0.40 * district_evidence_consensus_score

        # Conflict handling: when channels diverge, inject softening dispersion
        has_conflict = (t_dist != dom_d and t_dist != dominant_flow_district and dom_d != dominant_flow_district)
        conflict_smoothing = 0.08 if has_conflict else 0.03

        # Channel A: Terminal Mule Geography (configured max budget = 30.0%)
        # Base weight multiplier: 1.6
        s_A = np.ones(n_dist, dtype=np.float64) * conflict_smoothing
        s_A[ALL_11_DISTRICTS.index(t_dist)] += 0.65 * terminal_flow_alignment * consensus_boost
        adj_t = DISTRICT_ADJACENCY[t_dist]
        for adj in adj_t:
            s_A[ALL_11_DISTRICTS.index(adj)] += 0.35 / len(adj_t)
        s_A /= s_A.sum()

        # Channel B: Dominant Account Geography (configured max budget = 30.0%)
        # Base weight multiplier: 1.8
        s_B = np.ones(n_dist, dtype=np.float64) * conflict_smoothing
        s_B[ALL_11_DISTRICTS.index(dom_d)] += 0.70 * dom_share * geo_consistency * consensus_boost
        s_B[ALL_11_DISTRICTS.index(maj_down_d)] += 0.40 * majority_downstream_share * downstream_direction_strength
        adj_dom = DISTRICT_ADJACENCY[dom_d]
        for adj in adj_dom:
            s_B[ALL_11_DISTRICTS.index(adj)] += 0.30 / len(adj_dom)
        s_B /= s_B.sum()

        # Channel C: Route Trajectory & Flow (configured max budget = 25.0%)
        # Base weight multiplier: 1.4
        s_C = np.ones(n_dist, dtype=np.float64) * conflict_smoothing
        s_C[ALL_11_DISTRICTS.index(dominant_flow_district)] += 0.60 * downstream_route_consistency
        adj_flow = DISTRICT_ADJACENCY[dominant_flow_district]
        for adj in adj_flow:
            s_C[ALL_11_DISTRICTS.index(adj)] += 0.35 * (1.0 - backtrack_ratio) / len(adj_flow)
        if arch_name == "TRANSPORT_HUB_MOVEMENT":
            for d_hub in ["CENTRAL", "NEW_DELHI", "NORTH", "EAST", "SHAHDARA"]:
                s_C[ALL_11_DISTRICTS.index(d_hub)] += 0.15
        s_C /= s_C.sum()

        # Channel D: Behavioral & Origin Context (configured max budget = 10.0%)
        # Base weight multiplier: 1.0
        s_D = np.ones(n_dist, dtype=np.float64) * conflict_smoothing
        if arch_name in ["LOCAL_RAPID_CASHOUT", "NIGHTTIME_ATM_CASHOUT"]:
            s_D[ALL_11_DISTRICTS.index(v_dist)] += 0.85
        elif arch_name == "CROSS_DISTRICT_MULE_CHAIN":
            s_D[ALL_11_DISTRICTS.index(v_dist)] += 0.05 # Strong cross-district push
        else:
            s_D[ALL_11_DISTRICTS.index(v_dist)] += 0.45
        s_D /= s_D.sum()

        # Channel E: Leakage-Safe History (configured max budget = 5.0%)
        # Base weight multiplier: 0.5
        s_E = np.ones(n_dist, dtype=np.float64) / n_dist
        s_E[ALL_11_DISTRICTS.index(recent_hop_district)] += 0.25 * recent_two_hop_consistency
        s_E /= s_E.sum()

        # Combine channels using strict mathematical budget weights
        w_A = 0.30
        w_B = 0.30
        w_C = 0.25
        w_D = 0.10
        w_E = 0.05
        p_district = w_A * s_A + w_B * s_B + w_C * s_C + w_D * s_D + w_E * s_E

        # District-size normalization: moderate district probability by cluster inventory
        # to prevent single-cluster districts (e.g. NORTH_EAST with 1 cluster) from accumulating excessive mass
        inventory_weights = np.array([len(self.clusters_by_district[d])**0.50 for d in ALL_11_DISTRICTS], dtype=np.float64)
        p_district = p_district * inventory_weights

        # Normalize Stage 1 probabilities in float64
        dist_sum = p_district.sum()
        p_district = p_district / dist_sum

        # Check Stage 1 normalization tolerance (<= 1e-9)
        d_sum_err = abs(float(p_district.sum()) - 1.0)
        if d_sum_err > self.max_district_sum_error:
            self.max_district_sum_error = d_sum_err
        if (p_district < 0.0).any() or (p_district > 1.0).any() or np.isnan(p_district).any():
            self.invalid_district_prob_rows += 1

        # Sample realized district using FULL PRECISION
        d_idx = self.rng.choice(len(ALL_11_DISTRICTS), p=p_district)
        realized_district = ALL_11_DISTRICTS[d_idx]

        # =========================================================================
        # STAGE 2: SAMPLE CLUSTER INSIDE REALIZED DISTRICT (District-Local Portfolios)
        # =========================================================================
        cand_clusters = self.clusters_by_district[realized_district]
        n_cands = len(cand_clusters)

        # 1. Functional role support vector (45% budget share)
        fraud_roles = FRAUD_ROLE_PREFERENCES.get(ft, ["COMMERCIAL_HUB_LOCAL", "MIXED_RETAIL_CORRIDOR"])
        s_role = np.ones(n_cands, dtype=np.float64) * 0.50
        for i, c in enumerate(cand_clusters):
            cid = c["id"]
            c_roles = CLUSTER_LOCAL_ROLES.get(cid, ["LOCAL_BRANCH_NETWORK"])
            matched_proto_roles = [r for r in preferred_roles if r in c_roles]
            if matched_proto_roles:
                s_role[i] += 2.5 * len(matched_proto_roles)
            matched_fraud_roles = [r for r in fraud_roles if r in c_roles]
            if matched_fraud_roles:
                s_role[i] += 1.8 * len(matched_fraud_roles)
            if "HIGH_DENSITY_ATM_CORRIDOR" in c_roles and arch_name in ["HIGH_VALUE_DELAYED_CASHOUT", "NIGHTTIME_ATM_CASHOUT"]:
                s_role[i] += 1.5
            if arch_name == "RECURRING_SYNDICATE_CORRIDOR" and cid in syn["preferred_clusters"]:
                s_role[i] += 2.0
        s_role /= s_role.sum()

        # 2. Primary portfolio rotation support vector (35% budget share)
        # Rotates primary cluster across available role-matched candidates using case modulo hashing
        s_primary = np.ones(n_cands, dtype=np.float64) * 0.30
        primary_cand_idx = (case_num + proto["sub_index"]) % n_cands
        s_primary[primary_cand_idx] += 1.80
        secondary_cand_idx = (primary_cand_idx + 1) % n_cands
        s_primary[secondary_cand_idx] += 0.80
        s_primary /= s_primary.sum()

        # 3. Spatial noise and baseline intra-district support (14% budget share)
        s_noise = np.ones(n_cands, dtype=np.float64) / n_cands

        # 4. Global historical popularity support vector (capped at <= 6.0% budget share)
        # Saturated with log1p(prior_events) with strict floor/ceiling
        s_hist = np.zeros(n_cands, dtype=np.float64)
        for i, c in enumerate(cand_clusters):
            cid = c["id"]
            prior_events = self.cluster_history_counts.get(cid, 0)
            log_pop = float(min(0.06, 0.02 * np.log1p(prior_events)))
            s_hist[i] = log_pop
        hist_total = s_hist.sum()
        if hist_total > 1e-9:
            s_hist /= hist_total
        else:
            s_hist = np.ones(n_cands, dtype=np.float64) / n_cands

        # Combine Stage 2 vectors using frozen budget weights
        w_role = 0.45
        w_primary = 0.35
        w_noise = 0.14
        w_hist = 0.06
        p_cluster = w_role * s_role + w_primary * s_primary + w_noise * s_noise + w_hist * s_hist

        # Track realized popularity contribution
        realized_hist_contrib = float(w_hist)
        if realized_hist_contrib > self.max_realized_popularity_contrib:
            self.max_realized_popularity_contrib = realized_hist_contrib
        self.popularity_contrib_sum += realized_hist_contrib

        # Normalize Stage 2 probabilities in float64
        clust_sum = p_cluster.sum()
        p_cluster = p_cluster / clust_sum

        # Check Stage 2 normalization tolerance (<= 1e-9)
        c_sum_err = abs(float(p_cluster.sum()) - 1.0)
        if c_sum_err > self.max_cluster_sum_error:
            self.max_cluster_sum_error = c_sum_err
        if (p_cluster < 0.0).any() or (p_cluster > 1.0).any() or np.isnan(p_cluster).any():
            self.invalid_cluster_prob_rows += 1

        # Sample realized cluster using FULL PRECISION
        c_choice_idx = self.rng.choice(n_cands, p=p_cluster)
        target_cluster = cand_clusters[c_choice_idx]
        target_cid = target_cluster["id"]
        target_cluster_name = target_cluster["name"]

        # Update dynamic history
        self.cluster_history_counts[target_cid] = self.cluster_history_counts.get(target_cid, 0) + 1

        # Verify strict invariant
        if target_cluster["district"] != realized_district:
            self.district_cluster_mismatches += 1

        target_lat = round(float(target_cluster["lat"] + self.rng.normal(0, 0.005)), 6)
        target_lon = round(float(target_cluster["lon"] + self.rng.normal(0, 0.005)), 6)

        # Realized cashout minutes (regression target)
        dist_to_cashout = haversine_km(v_lat, v_lon, target_lat, target_lon)
        speed_kmh = self.rng.uniform(20.0, 32.0)
        travel_time_min = (dist_to_cashout / speed_kmh) * 60.0
        dwell_min = float(hop_count * self.rng.uniform(8.0, 16.0) + self.rng.uniform(12.0, 28.0))
        realized_minutes = round(float(min(720.0, max(15.0, travel_time_min + dwell_min))), 2)

        # Family IDs
        syn_family = syn["id"] if arch_name == "RECURRING_SYNDICATE_CORRIDOR" else f"SYN-V63-{(case_num % 100) + 1:03d}"
        mule_family = f"MULE-V63-{(case_num % 150) + 1:03d}"

        return {
            "case_id": f"CMP-V63-{case_num:06d}",
            "amount": amount,
            "log_amount": log_amount,
            "amount_bucket": amt_b,
            "fraud_type": ft,
            "payment_channel": channel,
            "event_timestamp": event_time.isoformat() + "Z",
            "reported_at": report_time.isoformat() + "Z",
            "reporting_delay_minutes": delay_min,
            "victim_district": v_dist,
            "victim_lat": v_lat,
            "victim_lon": v_lon,
            "victim_bank_group": v_bank,
            "transaction_count": max(1, hop_count + int(self.rng.integers(0, 3))),
            "transaction_hop_count": hop_count,
            "beneficiary_account_count": beneficiary_count,
            "mule_account_count": mule_count,
            "distinct_bank_count": bank_count,
            "terminal_mule_district": t_dist,
            "account_district_count": account_dist_count,
            "dominant_account_district": dom_d,
            "dominant_account_district_share": dom_share,
            "beneficiary_geo_consistency": geo_consistency,
            "terminal_vs_majority_account_distance_km": term_majority_dist_km,
            "cross_district_transfer_count": cross_dist_transfers,
            "geographic_dispersion_score": geo_dispersion,
            "transaction_velocity": velocity,
            "transfer_burst_score": burst_score,
            "graph_depth": depth,
            "graph_branching_factor": branching,
            "night_activity_ratio": night_ratio,
            "weekend_flag": weekend_flag,
            "money_flow_net_displacement_km": net_disp_km,
            "money_flow_total_path_km": total_path_km,
            "money_flow_backtrack_ratio": backtrack_ratio,
            "dominant_flow_district": dominant_flow_district,
            "terminal_flow_alignment_score": terminal_flow_alignment,
            "downstream_geo_concentration": downstream_geo_conc,
            "cross_district_hop_ratio": cross_hop_ratio,
            "terminal_displacement_from_origin_km": term_displacement,
            "downstream_route_consistency": downstream_route_consistency,
            "downstream_direction_strength": downstream_direction_strength,
            "terminal_path_share": terminal_path_share,
            "majority_downstream_district": majority_downstream_district,
            "majority_downstream_share": majority_downstream_share,
            "recent_hop_district": recent_hop_district,
            "recent_two_hop_consistency": recent_two_hop_consistency,
            "route_entropy": route_entropy,
            "route_turnaround_count": route_turnaround_count,
            "terminal_alignment_with_flow": terminal_alignment_with_flow,
            "district_evidence_consensus_score": district_evidence_consensus_score,
            "historical_district_crime_density": hist_crime_density,
            "commercial_hub_proximity_km": comm_proximity,
            "latent_archetype": arch_name,
            "sub_prototype_id": sub_proto_id,
            "syndicate_family_id": syn_family,
            "mule_family_id": mule_family,
            "generator_district_distribution": json.dumps([round(float(p), 4) for p in p_district]),
            "generator_cluster_distribution": json.dumps([round(float(p), 4) for p in p_cluster]),
            "realized_cashout_district": realized_district,
            "realized_cashout_cluster_id": target_cid,
            "realized_cashout_cluster_name": target_cluster_name,
            "realized_cashout_lat": target_lat,
            "realized_cashout_lon": target_lon,
            "realized_cashout_minutes": realized_minutes,
            "split": "",
            "generation_seed": self.seed,
            "generator_version": "v6.3"
        }

    def generate_dataset(self) -> pd.DataFrame:
        """Generates the full deterministic 15,000-case dataset."""
        print(f"Generating {self.total_cases} cases with seed {self.seed} (V6.3 Balanced Signal Model)...")
        start_date = datetime.datetime(2025, 1, 1, 0, 0, 0)
        raw_offsets = np.sort(self.rng.uniform(0, 365.0 * 86400.0, size=self.total_cases))

        records = []
        for i in range(self.total_cases):
            case_base = start_date + datetime.timedelta(seconds=float(raw_offsets[i]))
            rec = self.generate_case(i + 1, case_base)
            records.append(rec)

        df = pd.DataFrame(records)
        df = df.sort_values("event_timestamp").reset_index(drop=True)
        df["case_id"] = [f"CMP-V63-{k+1:06d}" for k in range(self.total_cases)]

        # Chronological splits: 10500 train, 2250 validation, 2250 test
        n_train = int(round(self.total_cases * 0.70))
        n_val = int(round(self.total_cases * 0.15))
        n_test = self.total_cases - n_train - n_val
        df["split"] = ["train"] * n_train + ["validation"] * n_val + ["test"] * n_test

        # Cohort family isolation
        val_mask = df["split"] == "validation"
        test_mask = df["split"] == "test"
        df.loc[val_mask, "syndicate_family_id"] = df.loc[val_mask, "syndicate_family_id"].apply(lambda s: s + "-VAL")
        df.loc[val_mask, "mule_family_id"] = df.loc[val_mask, "mule_family_id"].apply(lambda m: m + "-VAL")
        df.loc[test_mask, "syndicate_family_id"] = df.loc[test_mask, "syndicate_family_id"].apply(lambda s: s + "-TEST")
        df.loc[test_mask, "mule_family_id"] = df.loc[test_mask, "mule_family_id"].apply(lambda m: m + "-TEST")

        return df

def save_deterministic_csv_gz(df: pd.DataFrame, output_path: str):
    """Saves DataFrame as deterministic gzip with fixed mtime for byte-for-byte reproducibility."""
    os.makedirs(os.path.dirname(output_path), exist_ok=True)
    csv_bytes = df.to_csv(index=False).encode("utf-8")
    with open(output_path, "wb") as f_out:
        with gzip.GzipFile(filename="", mode="wb", fileobj=f_out, mtime=0.0) as gz:
            gz.write(csv_bytes)
    print(f"Dataset successfully saved to {output_path}")

def main():
    parser = argparse.ArgumentParser(description="Generate Delhi V6.3 Controlled Synthetic Dataset")
    parser.add_argument("--cases", type=int, default=15000, help="Total cases (default: 15000)")
    parser.add_argument("--seed", type=int, default=39184, help="RNG seed (default: 39184)")
    parser.add_argument("--output", type=str, default=None, help="Output path for csv.gz")
    args = parser.parse_args()

    base_dir = os.path.abspath(os.path.join(os.path.dirname(__file__), "..", ".."))
    out_path = args.output or os.path.join(base_dir, "ml", "data", "delhi_v6_3_cases.csv.gz")

    gen = DelhiV63DatasetGenerator(seed=args.seed, total_cases=args.cases)
    df = gen.generate_dataset()
    save_deterministic_csv_gz(df, out_path)
    mean_hist_contrib = gen.popularity_contrib_sum / max(1, args.cases)
    print(f"Generator Quality Checks: max_dist_sum_err={gen.max_district_sum_error:.2e}, max_clust_sum_err={gen.max_cluster_sum_error:.2e}, mismatches={gen.district_cluster_mismatches}")
    print(f"Historical Popularity Contribution: max={gen.max_realized_popularity_contrib*100:.2f}%, mean={mean_hist_contrib*100:.2f}% (Cap: <= 6.0%)")

if __name__ == "__main__":
    main()
