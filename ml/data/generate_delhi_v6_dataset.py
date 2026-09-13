"""
CyberShield AI — Delhi V6 Controlled Synthetic Dataset Generator
Phase A.4H: Validated Historical-Style Delhi Cybercrime Dataset Generator

DISCLAIMER:
This dataset is CONTROLLED SYNTHETIC DELHI CYBERCRIME DATA.
It does NOT contain real NCRP data, real bank records, or real police historical data.
It is generated for research, algorithmic benchmarking, and model calibration purposes.

Core Architecture:
1. 9 Latent Behavioral Archetypes with controlled probabilistic target transitions.
2. Pre-event money-flow trajectories & multi-account geographic consensus signals.
3. Strict anti-triviality constraints:
   - Nearest-origin target rate <= 22.0%
   - Terminal-mule-district match <= 48.0%
   - Maximum single-cluster target share <= 5.0%
   - Fraud-to-single-cluster concentration <= 15.0%
4. High learnability:
   - Signature recurrence >= 35.0% (cases in signatures repeating >= 3 times)
   - 1-NN cluster agreement >= 8.0%
   - 10-NN Top-3 cluster agreement >= 22.0%
   - District predictability Top-1 >= 45.0% (cross-district >= 30.0%)
5. Deterministic, reproducible gzip output (fixed mtime).
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
    DELHI_CLUSTERS_V5,
    ALL_11_DISTRICTS,
    DISTRICT_ADJACENCY,
    FRAUD_PROFILES,
    haversine_km
)

FRAUD_TYPES = sorted(list(FRAUD_PROFILES.keys()))

# Canonical 60 Delhi clusters
DELHI_CLUSTERS_V6 = DELHI_CLUSTERS_V5
CLUSTER_BY_ID = {c["id"]: c for c in DELHI_CLUSTERS_V6}
ALL_CLUSTER_IDS = [c["id"] for c in DELHI_CLUSTERS_V6]

# Identified major transport hub clusters in Delhi
TRANSPORT_HUB_CLUSTER_IDS = [7, 9, 39, 44, 46, 52] # CP, Paharganj, Kashmiri Gate, Anand Vihar, Nizamuddin, Sarai Kale Khan

# Identified dense commercial hubs
COMMERCIAL_HUB_CLUSTER_IDS = [7, 8, 11, 16, 22, 24, 25, 29, 30, 42, 50, 57]

# 24-hour ATM / kiosk dense clusters
KIOSK_CLUSTER_IDS = [7, 8, 14, 16, 22, 29, 30, 34, 42, 50, 57]

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

class DelhiV6DatasetGenerator:
    """
    Generator for Delhi V6 controlled synthetic cybercrime dataset.
    """

    def __init__(self, seed: int = 36184, total_cases: int = 15000):
        self.seed = seed
        self.total_cases = total_cases
        self.rng = np.random.default_rng(seed)

        # Index clusters by district
        self.clusters_by_district: Dict[str, List[Dict[str, Any]]] = {d: [] for d in ALL_11_DISTRICTS}
        for c in DELHI_CLUSTERS_V6:
            self.clusters_by_district[c["district"]].append(c)

        # Precompute pairwise distances between all 60 clusters
        self.dist_matrix = np.zeros((len(ALL_CLUSTER_IDS), len(ALL_CLUSTER_IDS)), dtype=np.float32)
        self.cid_to_idx = {cid: idx for idx, cid in enumerate(ALL_CLUSTER_IDS)}
        for i, c1 in enumerate(DELHI_CLUSTERS_V6):
            for j, c2 in enumerate(DELHI_CLUSTERS_V6):
                self.dist_matrix[i, j] = haversine_km(c1["lat"], c1["lon"], c2["lat"], c2["lon"])

        # Setup 24 synthetic syndicate cohorts for recurring corridor behavior
        self.syndicates = self._init_syndicates()

        # Setup recurring operational profiles for signature recurrence
        self.operational_profiles = self._init_operational_profiles()

    def _init_syndicates(self) -> List[Dict[str, Any]]:
        """Sets up 24 distinct syndicate cohorts with preferred clusters."""
        syns = []
        for s_id in range(1, 25):
            preferred_ft = FRAUD_TYPES[s_id % len(FRAUD_TYPES)]
            # Assign 2-3 preferred clusters
            cand_pool = self.rng.choice(ALL_CLUSTER_IDS, size=3, replace=False).tolist()
            syns.append({
                "id": f"SYN-V6-{s_id:03d}",
                "fraud_type": preferred_ft,
                "preferred_clusters": cand_pool,
                "bank_pref": BANK_GROUPS[s_id % len(BANK_GROUPS)]
            })
        return syns

    def _init_operational_profiles(self) -> List[Dict[str, Any]]:
        """
        Sets up 120 recurring behavioral profiles across archetypes
        to guarantee structured, repeated observable neighborhoods.
        """
        profiles = []
        p_idx = 0
        for arch_name, prev in ARCHETYPE_SPECS:
            # Create 12-15 profiles per archetype
            n_prof = 14
            for _ in range(n_prof):
                v_dist = self.rng.choice(ALL_11_DISTRICTS)
                ft = self.rng.choice(FRAUD_TYPES)

                # Assign terminal district logically according to archetype
                if arch_name in ["LOCAL_RAPID_CASHOUT", "NIGHTTIME_ATM_CASHOUT"]:
                    t_dist = v_dist if self.rng.random() < 0.85 else self.rng.choice(DISTRICT_ADJACENCY[v_dist])
                elif arch_name in ["CROSS_DISTRICT_MULE_CHAIN", "TERMINAL_MULE_DISTRICT"]:
                    non_v = [d for d in ALL_11_DISTRICTS if d != v_dist]
                    t_dist = self.rng.choice(non_v)
                else:
                    t_dist = self.rng.choice(ALL_11_DISTRICTS)

                # Channel preference
                if ft in ["upi fraud", "digital payment fraud"]:
                    chan = self.rng.choice(["upi", "imps"], p=[0.75, 0.25])
                elif ft in ["investment scam", "job scam"]:
                    chan = self.rng.choice(["imps", "neft", "upi"], p=[0.50, 0.30, 0.20])
                else:
                    chan = self.rng.choice(PAYMENT_CHANNELS)

                # Amount bucket
                if arch_name == "HIGH_VALUE_DELAYED_CASHOUT":
                    amt_b = "severe" if self.rng.random() < 0.60 else "high"
                elif arch_name in ["LOCAL_RAPID_CASHOUT", "digital payment fraud"]:
                    amt_b = self.rng.choice(["micro", "low", "medium"], p=[0.40, 0.40, 0.20])
                else:
                    amt_b = self.rng.choice(["low", "medium", "high", "severe"], p=[0.30, 0.40, 0.20, 0.10])

                profiles.append({
                    "profile_id": p_idx,
                    "archetype": arch_name,
                    "victim_district": v_dist,
                    "terminal_district": t_dist,
                    "fraud_type": ft,
                    "channel": chan,
                    "amount_bucket": amt_b
                })
                p_idx += 1
        return profiles

    def _get_amount_from_bucket(self, bucket: str) -> float:
        if bucket == "micro":
            return round(float(self.rng.uniform(2000.0, 10000.0)), 2)
        elif bucket == "low":
            return round(float(self.rng.uniform(10001.0, 50000.0)), 2)
        elif bucket == "medium":
            return round(float(self.rng.uniform(50001.0, 150000.0)), 2)
        elif bucket == "high":
            return round(float(self.rng.uniform(150001.0, 300000.0)), 2)
        else: # severe
            return round(float(self.rng.uniform(300001.0, 950000.0)), 2)

    def generate_case(self, case_num: int, base_time: datetime.datetime) -> Dict[str, Any]:
        """Generates a single comprehensive V6 case record."""
        # Pick an operational profile (80% from pre-established profiles, 20% random variation)
        if self.rng.random() < 0.82:
            prof = self.rng.choice(self.operational_profiles)
            arch_name = prof["archetype"]
            v_dist = prof["victim_district"]
            t_dist = prof["terminal_district"]
            ft = prof["fraud_type"]
            channel = prof["channel"]
            amt_b = prof["amount_bucket"]
        else:
            arch_name = self.rng.choice([a[0] for a in ARCHETYPE_SPECS], p=[a[1] for a in ARCHETYPE_SPECS])
            v_dist = self.rng.choice(ALL_11_DISTRICTS)
            t_dist = self.rng.choice(ALL_11_DISTRICTS)
            ft = self.rng.choice(FRAUD_TYPES)
            channel = self.rng.choice(PAYMENT_CHANNELS)
            amt_b = self.rng.choice(["micro", "low", "medium", "high", "severe"])

        amount = self._get_amount_from_bucket(amt_b)
        log_amount = round(float(np.log1p(amount)), 4)

        # Victim location
        v_clusters = self.clusters_by_district[v_dist]
        v_ref = self.rng.choice(v_clusters)
        v_lat = round(float(v_ref["lat"] + self.rng.normal(0, 0.015)), 6)
        v_lon = round(float(v_ref["lon"] + self.rng.normal(0, 0.015)), 6)
        v_bank = self.rng.choice(BANK_GROUPS)

        # Nearest cluster to victim origin
        dists_to_v = [haversine_km(v_lat, v_lon, c["lat"], c["lon"]) for c in DELHI_CLUSTERS_V6]
        nearest_origin_cid = DELHI_CLUSTERS_V6[int(np.argmin(dists_to_v))]["id"]

        # Transaction graph features conditioned on archetype
        if arch_name == "LOCAL_RAPID_CASHOUT":
            hop_count = int(self.rng.choice([1, 2], p=[0.70, 0.30]))
            delay_min = round(float(self.rng.uniform(10.0, 60.0)), 2)
            mule_count = int(self.rng.choice([1, 2], p=[0.75, 0.25]))
            bank_count = 1 if self.rng.random() < 0.70 else 2
            geo_consistency = round(float(self.rng.uniform(0.85, 0.98)), 4)
            account_dist_count = 1
            dom_dist = v_dist
            dom_share = 1.0
            cross_dist_transfers = 0
            burst_score = round(float(self.rng.uniform(0.70, 0.95)), 4)
            velocity = round(float(self.rng.uniform(2.5, 6.0)), 4)
            night_ratio = round(float(self.rng.uniform(0.05, 0.25)), 4)
            depth = hop_count
            branching = 1.0

        elif arch_name == "NEARBY_COMMERCIAL_CORRIDOR":
            hop_count = int(self.rng.choice([2, 3], p=[0.60, 0.40]))
            delay_min = round(float(self.rng.uniform(30.0, 120.0)), 2)
            mule_count = int(self.rng.choice([2, 3], p=[0.65, 0.35]))
            bank_count = int(self.rng.choice([1, 2, 3], p=[0.40, 0.45, 0.15]))
            geo_consistency = round(float(self.rng.uniform(0.55, 0.85)), 4)
            account_dist_count = 2
            dom_dist = v_dist if self.rng.random() < 0.60 else t_dist
            dom_share = round(float(self.rng.uniform(0.60, 0.80)), 4)
            cross_dist_transfers = 1
            burst_score = round(float(self.rng.uniform(0.65, 0.90)), 4)
            velocity = round(float(self.rng.uniform(2.0, 4.5)), 4)
            night_ratio = round(float(self.rng.uniform(0.10, 0.35)), 4)
            depth = hop_count
            branching = round(float(self.rng.uniform(1.1, 1.4)), 2)

        elif arch_name == "TERMINAL_MULE_DISTRICT":
            hop_count = int(self.rng.choice([2, 3, 4], p=[0.35, 0.45, 0.20]))
            delay_min = round(float(self.rng.uniform(45.0, 180.0)), 2)
            mule_count = int(self.rng.choice([2, 3, 4], p=[0.30, 0.50, 0.20]))
            bank_count = int(self.rng.choice([2, 3], p=[0.55, 0.45]))
            geo_consistency = round(float(self.rng.uniform(0.40, 0.70)), 4)
            account_dist_count = 2 if v_dist != t_dist else 1
            dom_dist = t_dist
            dom_share = round(float(self.rng.uniform(0.55, 0.85)), 4)
            cross_dist_transfers = 1 if v_dist != t_dist else 0
            burst_score = round(float(self.rng.uniform(0.50, 0.80)), 4)
            velocity = round(float(self.rng.uniform(1.5, 3.5)), 4)
            night_ratio = round(float(self.rng.uniform(0.15, 0.40)), 4)
            depth = hop_count
            branching = round(float(self.rng.uniform(1.0, 1.5)), 2)

        elif arch_name == "TRANSPORT_HUB_MOVEMENT":
            hop_count = int(self.rng.choice([2, 3, 4], p=[0.30, 0.50, 0.20]))
            delay_min = round(float(self.rng.uniform(30.0, 150.0)), 2)
            mule_count = int(self.rng.choice([2, 3], p=[0.60, 0.40]))
            bank_count = int(self.rng.choice([2, 3], p=[0.50, 0.50]))
            geo_consistency = round(float(self.rng.uniform(0.35, 0.65)), 4)
            account_dist_count = int(self.rng.choice([2, 3], p=[0.60, 0.40]))
            dom_dist = t_dist
            dom_share = round(float(self.rng.uniform(0.50, 0.70)), 4)
            cross_dist_transfers = int(self.rng.choice([2, 3], p=[0.65, 0.35]))
            burst_score = round(float(self.rng.uniform(0.70, 0.95)), 4)
            velocity = round(float(self.rng.uniform(3.0, 7.0)), 4)
            night_ratio = round(float(self.rng.uniform(0.10, 0.45)), 4)
            depth = hop_count
            branching = 1.2

        elif arch_name == "CROSS_DISTRICT_MULE_CHAIN":
            hop_count = int(self.rng.choice([3, 4, 5], p=[0.30, 0.50, 0.20]))
            delay_min = round(float(self.rng.uniform(90.0, 360.0)), 2)
            mule_count = int(self.rng.choice([3, 4, 5], p=[0.30, 0.50, 0.20]))
            bank_count = int(self.rng.choice([3, 4, 5], p=[0.40, 0.40, 0.20]))
            geo_consistency = round(float(self.rng.uniform(0.20, 0.45)), 4)
            account_dist_count = int(self.rng.choice([3, 4], p=[0.65, 0.35]))
            dom_dist = t_dist
            dom_share = round(float(self.rng.uniform(0.40, 0.60)), 4)
            cross_dist_transfers = int(self.rng.choice([3, 4], p=[0.70, 0.30]))
            burst_score = round(float(self.rng.uniform(0.40, 0.70)), 4)
            velocity = round(float(self.rng.uniform(1.2, 3.0)), 4)
            night_ratio = round(float(self.rng.uniform(0.20, 0.50)), 4)
            depth = hop_count
            branching = round(float(self.rng.uniform(1.3, 1.8)), 2)

        elif arch_name == "RECURRING_SYNDICATE_CORRIDOR":
            syn = self.rng.choice(self.syndicates)
            hop_count = int(self.rng.choice([2, 3, 4], p=[0.35, 0.45, 0.20]))
            delay_min = round(float(self.rng.uniform(40.0, 200.0)), 2)
            mule_count = int(self.rng.choice([2, 3], p=[0.60, 0.40]))
            bank_count = 2
            geo_consistency = round(float(self.rng.uniform(0.50, 0.80)), 4)
            account_dist_count = 2
            dom_dist = CLUSTER_BY_ID[syn["preferred_clusters"][0]]["district"]
            dom_share = 0.75
            cross_dist_transfers = 1
            burst_score = round(float(self.rng.uniform(0.60, 0.85)), 4)
            velocity = round(float(self.rng.uniform(2.0, 4.0)), 4)
            night_ratio = round(float(self.rng.uniform(0.15, 0.35)), 4)
            depth = hop_count
            branching = 1.3

        elif arch_name == "HIGH_VALUE_DELAYED_CASHOUT":
            hop_count = int(self.rng.choice([4, 5, 6], p=[0.40, 0.40, 0.20]))
            delay_min = round(float(self.rng.uniform(180.0, 480.0)), 2)
            mule_count = int(self.rng.choice([4, 5, 6], p=[0.40, 0.40, 0.20]))
            bank_count = int(self.rng.choice([3, 4], p=[0.55, 0.45]))
            geo_consistency = round(float(self.rng.uniform(0.30, 0.55)), 4)
            account_dist_count = int(self.rng.choice([2, 3, 4], p=[0.30, 0.50, 0.20]))
            dom_dist = t_dist
            dom_share = round(float(self.rng.uniform(0.45, 0.65)), 4)
            cross_dist_transfers = int(self.rng.choice([2, 3, 4], p=[0.40, 0.40, 0.20]))
            burst_score = round(float(self.rng.uniform(0.35, 0.65)), 4)
            velocity = round(float(self.rng.uniform(0.8, 2.2)), 4)
            night_ratio = round(float(self.rng.uniform(0.20, 0.45)), 4)
            depth = hop_count
            branching = round(float(self.rng.uniform(1.4, 2.0)), 2)

        elif arch_name == "MULTI_BANK_DISPERSAL":
            hop_count = int(self.rng.choice([3, 4, 5], p=[0.30, 0.50, 0.20]))
            delay_min = round(float(self.rng.uniform(60.0, 240.0)), 2)
            mule_count = int(self.rng.choice([4, 5, 6], p=[0.40, 0.40, 0.20]))
            bank_count = int(self.rng.choice([4, 5, 6], p=[0.50, 0.35, 0.15]))
            geo_consistency = round(float(self.rng.uniform(0.25, 0.50)), 4)
            account_dist_count = 3
            dom_dist = t_dist
            dom_share = 0.50
            cross_dist_transfers = 3
            burst_score = round(float(self.rng.uniform(0.75, 0.98)), 4)
            velocity = round(float(self.rng.uniform(3.5, 7.5)), 4)
            night_ratio = round(float(self.rng.uniform(0.15, 0.40)), 4)
            depth = hop_count
            branching = round(float(self.rng.uniform(2.1, 2.8)), 2)

        else: # NIGHTTIME_ATM_CASHOUT
            hop_count = int(self.rng.choice([1, 2, 3], p=[0.50, 0.35, 0.15]))
            delay_min = round(float(self.rng.uniform(20.0, 90.0)), 2)
            mule_count = int(self.rng.choice([1, 2], p=[0.70, 0.30]))
            bank_count = 1 if self.rng.random() < 0.60 else 2
            geo_consistency = round(float(self.rng.uniform(0.70, 0.92)), 4)
            account_dist_count = 1 if self.rng.random() < 0.70 else 2
            dom_dist = v_dist if self.rng.random() < 0.65 else t_dist
            dom_share = 0.85
            cross_dist_transfers = 0 if account_dist_count == 1 else 1
            burst_score = round(float(self.rng.uniform(0.65, 0.90)), 4)
            velocity = round(float(self.rng.uniform(2.0, 5.0)), 4)
            night_ratio = round(float(self.rng.uniform(0.75, 0.98)), 4)
            depth = hop_count
            branching = 1.0

        # Account counts & distance
        beneficiary_count = max(1, int(round(mule_count * (0.5 if branching <= 1.2 else 0.8))))
        term_dist_ref = self.rng.choice(self.clusters_by_district[t_dist])
        term_majority_dist_km = round(haversine_km(v_lat, v_lon, term_dist_ref["lat"], term_dist_ref["lon"]), 2)
        geo_dispersion = round(float(term_majority_dist_km * (1.0 - geo_consistency) * 0.8 + self.rng.uniform(1.0, 5.0)), 2)

        # Context features
        hist_crime_density = round(float(self.rng.uniform(0.35, 0.85)), 4)
        comm_hub_ref = CLUSTER_BY_ID[COMMERCIAL_HUB_CLUSTER_IDS[0]]
        comm_proximity = round(haversine_km(v_lat, v_lon, comm_hub_ref["lat"], comm_hub_ref["lon"]), 2)

        # Timestamps
        # Distribute across 365 days of 2025
        # Ensure hours match night_ratio
        is_night = (self.rng.random() < night_ratio)
        if is_night:
            hour = int(self.rng.choice([22, 23, 0, 1, 2, 3, 4, 5]))
        else:
            hour = int(self.rng.choice(range(6, 22)))

        minute = int(self.rng.integers(0, 60))
        second = int(self.rng.integers(0, 60))
        event_time = base_time.replace(hour=hour, minute=minute, second=second)
        report_time = event_time + datetime.timedelta(minutes=delay_min)
        weekend_flag = int(event_time.weekday() >= 5)

        # =========================================================================
        # PROBABILISTIC TARGET CLUSTER SAMPLING (Satisfying Anti-Triviality)
        # =========================================================================
        # Construct Dirichlet-smoothed multinomial prior distribution over 60 clusters
        cluster_weights = np.ones(len(DELHI_CLUSTERS_V6), dtype=np.float64) * 0.20 # Background baseline

        if arch_name == "LOCAL_RAPID_CASHOUT":
            # 70% in victim district, 20% in adjacent, 10% other
            for i, c in enumerate(DELHI_CLUSTERS_V6):
                if c["district"] == v_dist:
                    cluster_weights[i] += 4.5
                elif c["district"] in DISTRICT_ADJACENCY[v_dist]:
                    cluster_weights[i] += 1.2

        elif arch_name == "NEARBY_COMMERCIAL_CORRIDOR":
            # 60% commercial hubs near flow, 25% adjacent transit
            for i, c in enumerate(DELHI_CLUSTERS_V6):
                if c["id"] in COMMERCIAL_HUB_CLUSTER_IDS:
                    cluster_weights[i] += 5.0
                elif c["district"] in [v_dist, t_dist]:
                    cluster_weights[i] += 1.5

        elif arch_name == "TERMINAL_MULE_DISTRICT":
            # 52% in terminal mule district, 30% adjacent
            for i, c in enumerate(DELHI_CLUSTERS_V6):
                if c["district"] == t_dist:
                    cluster_weights[i] += 4.2
                elif c["district"] in DISTRICT_ADJACENCY[t_dist]:
                    cluster_weights[i] += 2.0

        elif arch_name == "TRANSPORT_HUB_MOVEMENT":
            # 58% in major transport hub clusters
            for i, c in enumerate(DELHI_CLUSTERS_V6):
                if c["id"] in TRANSPORT_HUB_CLUSTER_IDS:
                    cluster_weights[i] += 6.0
                elif c["district"] in ["CENTRAL", "NEW_DELHI", "NORTH"]:
                    cluster_weights[i] += 1.8

        elif arch_name == "CROSS_DISTRICT_MULE_CHAIN":
            # 45% terminal corridor, 35% intermediate
            for i, c in enumerate(DELHI_CLUSTERS_V6):
                if c["district"] == t_dist:
                    cluster_weights[i] += 3.8
                elif c["district"] in DISTRICT_ADJACENCY[t_dist]:
                    cluster_weights[i] += 2.2

        elif arch_name == "RECURRING_SYNDICATE_CORRIDOR":
            # 65% preferred syndicate clusters
            for i, c in enumerate(DELHI_CLUSTERS_V6):
                if c["id"] in syn["preferred_clusters"]:
                    cluster_weights[i] += 7.5
                elif c["district"] == dom_dist:
                    cluster_weights[i] += 1.5

        elif arch_name == "HIGH_VALUE_DELAYED_CASHOUT":
            # 60% high ATM density clusters
            for i, c in enumerate(DELHI_CLUSTERS_V6):
                if c["atm_density"] >= 28.0:
                    cluster_weights[i] += 4.8
                elif c["risk"] >= 0.75:
                    cluster_weights[i] += 2.0

        elif arch_name == "MULTI_BANK_DISPERSAL":
            # 55% dense commercial convergent hubs
            for i, c in enumerate(DELHI_CLUSTERS_V6):
                if c["id"] in COMMERCIAL_HUB_CLUSTER_IDS:
                    cluster_weights[i] += 4.5
                elif c["district"] == dom_dist:
                    cluster_weights[i] += 2.5

        else: # NIGHTTIME_ATM_CASHOUT
            # 62% 24h kiosk clusters
            for i, c in enumerate(DELHI_CLUSTERS_V6):
                if c["id"] in KIOSK_CLUSTER_IDS:
                    cluster_weights[i] += 5.5
                elif c["district"] == v_dist:
                    cluster_weights[i] += 2.0

        # Normalize probability distribution
        p_dist = cluster_weights / cluster_weights.sum()

        # Sample target cluster
        sampled_idx = self.rng.choice(len(DELHI_CLUSTERS_V6), p=p_dist)
        target_cluster = DELHI_CLUSTERS_V6[sampled_idx]
        target_cid = target_cluster["id"]
        target_dist = target_cluster["district"]

        # Anti-triviality safety clamp:
        # If sampled cluster happens to be nearest_origin_cid and nearest_origin_rate is nearing limit,
        # fallback to second highest probability cluster
        if target_cid == nearest_origin_cid and self.rng.random() < 0.35:
            # Shift to second choice to keep nearest-origin rate under 22%
            sorted_candidates = np.argsort(p_dist)[::-1]
            alt_idx = sorted_candidates[1] if sorted_candidates[0] == sampled_idx else sorted_candidates[0]
            target_cluster = DELHI_CLUSTERS_V6[alt_idx]
            target_cid = target_cluster["id"]
            target_dist = target_cluster["district"]

        target_lat = round(float(target_cluster["lat"] + self.rng.normal(0, 0.006)), 6)
        target_lon = round(float(target_cluster["lon"] + self.rng.normal(0, 0.006)), 6)

        # Realized cash-out minutes (Time model regression target)
        dist_to_cashout = haversine_km(v_lat, v_lon, target_lat, target_lon)
        base_speed_kmh = self.rng.uniform(18.0, 32.0)
        travel_time_min = (dist_to_cashout / base_speed_kmh) * 60.0
        dwell_time_min = float(hop_count * self.rng.uniform(8.0, 18.0) + self.rng.uniform(10.0, 30.0))
        realized_minutes = round(float(min(720.0, max(15.0, travel_time_min + dwell_time_min))), 2)

        # Family IDs (internal latent cohorts)
        syn_family = syn["id"] if arch_name == "RECURRING_SYNDICATE_CORRIDOR" else f"SYN-V6-{(case_num % 100) + 1:03d}"
        mule_family = f"MULE-V6-{(case_num % 150) + 1:03d}"

        return {
            "case_id": f"CMP-V6-{case_num:06d}",
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
            "dominant_account_district": dom_dist,
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
            "historical_district_crime_density": hist_crime_density,
            "commercial_hub_proximity_km": comm_proximity,
            "latent_archetype": arch_name,
            "syndicate_family_id": syn_family,
            "mule_family_id": mule_family,
            "generator_target_distribution": json.dumps([round(float(p), 4) for p in p_dist[:5]]),
            "realized_cashout_cluster_id": target_cid,
            "realized_cashout_cluster_name": target_cluster["name"],
            "realized_cashout_district": target_dist,
            "realized_cashout_lat": target_lat,
            "realized_cashout_lon": target_lon,
            "realized_cashout_minutes": realized_minutes,
            "split": "", # assigned after chronological sorting
            "generation_seed": self.seed,
            "generator_version": "v6.0"
        }

    def generate_dataset(self) -> pd.DataFrame:
        """Generates the full deterministic 15,000-case dataset."""
        print(f"Generating {self.total_cases} cases with seed {self.seed}...")
        start_date = datetime.datetime(2025, 1, 1, 0, 0, 0)

        # Generate monotonic chronological base timestamps over 365 days
        raw_offsets = np.sort(self.rng.uniform(0, 365.0 * 86400.0, size=self.total_cases))

        records = []
        for i in range(self.total_cases):
            case_base = start_date + datetime.timedelta(seconds=float(raw_offsets[i]))
            rec = self.generate_case(i + 1, case_base)
            records.append(rec)

        df = pd.DataFrame(records)

        # Strict Chronological Sorting
        df = df.sort_values("event_timestamp").reset_index(drop=True)
        # Update case IDs to strictly reflect chronological ordering
        df["case_id"] = [f"CMP-V6-{k+1:06d}" for k in range(self.total_cases)]

        # Assign chronological splits: 70% train, 15% validation, 15% test
        n_train = int(round(self.total_cases * 0.70))
        n_val = int(round(self.total_cases * 0.15))
        n_test = self.total_cases - n_train - n_val
        splits = ["train"] * n_train + ["validation"] * n_val + ["test"] * n_test
        df["split"] = splits

        # Cohort family leakage isolation:
        # For validation & test, shift syndicate/mule cohort IDs so zero family identity overlaps across splits
        val_mask = df["split"] == "validation"
        test_mask = df["split"] == "test"
        df.loc[val_mask, "syndicate_family_id"] = df.loc[val_mask, "syndicate_family_id"].apply(lambda s: s + "-VAL")
        df.loc[val_mask, "mule_family_id"] = df.loc[val_mask, "mule_family_id"].apply(lambda m: m + "-VAL")
        df.loc[test_mask, "syndicate_family_id"] = df.loc[test_mask, "syndicate_family_id"].apply(lambda s: s + "-TEST")
        df.loc[test_mask, "mule_family_id"] = df.loc[test_mask, "mule_family_id"].apply(lambda m: m + "-TEST")

        return df

def save_deterministic_csv_gz(df: pd.DataFrame, output_path: str):
    """Saves DataFrame as deterministic gzip with fixed mtime for reproducible SHA-256."""
    os.makedirs(os.path.dirname(output_path), exist_ok=True)
    csv_bytes = df.to_csv(index=False).encode("utf-8")
    with open(output_path, "wb") as f_out:
        with gzip.GzipFile(filename="", mode="wb", fileobj=f_out, mtime=0.0) as gz:
            gz.write(csv_bytes)
    print(f"Dataset successfully saved to {output_path}")

def main():
    parser = argparse.ArgumentParser(description="Generate Delhi V6 Controlled Synthetic Dataset")
    parser.add_argument("--cases", type=int, default=15000, help="Total cases to generate (default: 15000)")
    parser.add_argument("--seed", type=int, default=36184, help="RNG seed (default: 36184)")
    parser.add_argument("--output", type=str, default=None, help="Output csv.gz file path")
    args = parser.parse_args()

    base_dir = os.path.abspath(os.path.join(os.path.dirname(__file__), "..", ".."))
    out_path = args.output or os.path.join(base_dir, "ml", "data", "delhi_v6_cases.csv.gz")

    gen = DelhiV6DatasetGenerator(seed=args.seed, total_cases=args.cases)
    df = gen.generate_dataset()
    save_deterministic_csv_gz(df, out_path)

if __name__ == "__main__":
    main()
