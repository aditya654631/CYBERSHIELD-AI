"""
CyberShield AI — Delhi V6.1 Controlled Synthetic Dataset Generator
Phase A.4J: One-Shot Implementation of V6.1 Geographic Learnability Dataset

DISCLAIMER:
This dataset is CONTROLLED SYNTHETIC DELHI CYBERCRIME DATA.
It does NOT contain real NCRP data, real bank records, or real police historical data.
It is generated for research, algorithmic benchmarking, and model calibration purposes.

Key Enhancements over V6.0:
1. Explicit Two-Stage Hierarchical Target Generation:
   - Stage 1: P(cashout_district | observables) across 11 revenue districts
   - Stage 2: P(cashout_cluster | realized_district, archetype, observables) strictly within realized district
   - Invariant: cluster_district(realized_cluster) == realized_district for 100% of rows.
2. Probability Normalization:
   - Strict normalization for district and cluster probabilities (sum error <= 1e-9).
3. 54 Latent Behavioral Sub-Prototypes (9 archetypes x 6 sub-prototypes) providing
   learnable observable neighborhoods without deterministic target shortcuts.
4. Pre-event Money-Flow Trajectory & Downstream Geographic Consensus Observables.
5. Anti-triviality constraints strictly enforced (nearest-origin <= 22%, terminal-mule <= 48%).
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
    DELHI_CLUSTERS_V5 as DELHI_CLUSTERS_V6,
    ALL_11_DISTRICTS,
    DISTRICT_ADJACENCY,
    FRAUD_PROFILES,
    haversine_km
)

FRAUD_TYPES = sorted(list(FRAUD_PROFILES.keys()))
CLUSTER_BY_ID: Dict[int, Dict[str, Any]] = {c["id"]: c for c in DELHI_CLUSTERS_V6}
ALL_CLUSTER_IDS: List[int] = [c["id"] for c in DELHI_CLUSTERS_V6]

# Identified major functional clusters
TRANSPORT_HUB_CLUSTER_IDS = [7, 9, 39, 44, 46, 52] # CP, Paharganj, Kashmiri Gate, Anand Vihar, Nizamuddin, Sarai Kale Khan
COMMERCIAL_HUB_CLUSTER_IDS = [7, 8, 11, 16, 22, 24, 25, 29, 30, 42, 50, 57]
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

class DelhiV61DatasetGenerator:
    """
    Generator for Delhi V6.1 controlled synthetic cybercrime dataset.
    """

    def __init__(self, seed: int = 37184, total_cases: int = 15000):
        self.seed = seed
        self.total_cases = total_cases
        self.rng = np.random.default_rng(seed)

        # Index clusters by district
        self.clusters_by_district: Dict[str, List[Dict[str, Any]]] = {d: [] for d in ALL_11_DISTRICTS}
        for c in DELHI_CLUSTERS_V6:
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

        # Telemetry tracking for normalization & invariants
        self.max_district_sum_error = 0.0
        self.max_cluster_sum_error = 0.0
        self.invalid_district_prob_rows = 0
        self.invalid_cluster_prob_rows = 0
        self.district_cluster_mismatches = 0

    def _init_syndicates(self) -> List[Dict[str, Any]]:
        """Sets up 24 synthetic syndicate cohorts."""
        syns = []
        for s_id in range(1, 25):
            pref_ft = FRAUD_TYPES[s_id % len(FRAUD_TYPES)]
            pref_dist = ALL_11_DISTRICTS[s_id % len(ALL_11_DISTRICTS)]
            cands_in_dist = [c["id"] for c in self.clusters_by_district[pref_dist]]
            syns.append({
                "id": f"SYN-V61-{s_id:03d}",
                "base_district": pref_dist,
                "preferred_clusters": cands_in_dist[:3],
                "fraud_type": pref_ft
            })
        return syns

    def _init_sub_prototypes(self) -> List[Dict[str, Any]]:
        """Sets up 54 latent sub-prototypes (6 per archetype)."""
        protos = []
        proto_idx = 1
        for arch_name, _ in ARCHETYPE_SPECS:
            for sub_i in range(1, 7):
                v_dist = ALL_11_DISTRICTS[(proto_idx * 3) % len(ALL_11_DISTRICTS)]
                adj_dists = DISTRICT_ADJACENCY[v_dist]

                # Determine terminal & dominant districts logically
                if arch_name in ["LOCAL_RAPID_CASHOUT", "NIGHTTIME_ATM_CASHOUT"]:
                    t_dist = v_dist if sub_i <= 4 else adj_dists[0]
                    dom_d = v_dist
                elif arch_name in ["CROSS_DISTRICT_MULE_CHAIN", "TERMINAL_MULE_DISTRICT"]:
                    remote_dists = [d for d in ALL_11_DISTRICTS if d != v_dist and d not in adj_dists]
                    t_dist = remote_dists[sub_i % len(remote_dists)] if remote_dists else adj_dists[0]
                    dom_d = t_dist if sub_i <= 4 else adj_dists[0]
                elif arch_name == "TRANSPORT_HUB_MOVEMENT":
                    hub_dists = ["CENTRAL", "NEW_DELHI", "NORTH", "EAST"]
                    t_dist = hub_dists[sub_i % len(hub_dists)]
                    dom_d = t_dist
                elif arch_name == "RECURRING_SYNDICATE_CORRIDOR":
                    syn = self.syndicates[(proto_idx - 1) % len(self.syndicates)]
                    t_dist = syn["base_district"]
                    dom_d = t_dist
                else: # NEARBY_COMMERCIAL_CORRIDOR, HIGH_VALUE_DELAYED_CASHOUT, MULTI_BANK_DISPERSAL
                    t_dist = adj_dists[sub_i % len(adj_dists)]
                    dom_d = t_dist if sub_i % 2 == 0 else v_dist

                # Fraud type & channel
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
                    "sub_prototype_id": f"SUB-PROTO-{proto_idx:02d}",
                    "archetype": arch_name,
                    "sub_index": sub_i,
                    "victim_district": v_dist,
                    "terminal_mule_district": t_dist,
                    "dominant_account_district": dom_d,
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
        """Generates a single comprehensive V6.1 case record."""
        # 1. Select latent sub-prototype (85% from sub-prototypes, 15% mild perturbation)
        proto = self.rng.choice(self.sub_prototypes)
        arch_name = proto["archetype"]
        sub_proto_id = proto["sub_prototype_id"]
        v_dist = proto["victim_district"]
        t_dist = proto["terminal_mule_district"]
        dom_d = proto["dominant_account_district"]
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
        dists_to_v = [haversine_km(v_lat, v_lon, c["lat"], c["lon"]) for c in DELHI_CLUSTERS_V6]
        nearest_origin_cid = DELHI_CLUSTERS_V6[int(np.argmin(dists_to_v))]["id"]

        # Graph hops and delay conditioned on archetype
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
        comm_hub_ref = CLUSTER_BY_ID[COMMERCIAL_HUB_CLUSTER_IDS[0]]
        comm_proximity = round(haversine_km(v_lat, v_lon, comm_hub_ref["lat"], comm_hub_ref["lon"]), 2)

        # Timestamps
        is_night = (self.rng.random() < night_ratio)
        hour = int(self.rng.choice([22, 23, 0, 1, 2, 3, 4, 5])) if is_night else int(self.rng.choice(range(6, 22)))
        minute = int(self.rng.integers(0, 60))
        second = int(self.rng.integers(0, 60))
        event_time = base_time.replace(hour=hour, minute=minute, second=second)
        report_time = event_time + datetime.timedelta(minutes=delay_min)
        weekend_flag = int(event_time.weekday() >= 5)

        # =========================================================================
        # STAGE 1: SAMPLE CASH-OUT DISTRICT (Normalized across 11 Revenue Districts)
        # =========================================================================
        dist_weights = np.ones(len(ALL_11_DISTRICTS), dtype=np.float64) * 0.08 # Small baseline

        for i, d in enumerate(ALL_11_DISTRICTS):
            # Evidence from dominant account district
            if d == dom_d:
                dist_weights[i] += 3.8 * dom_share * geo_consistency
            # Evidence from terminal mule district
            if d == t_dist:
                dist_weights[i] += 3.2 * terminal_flow_alignment
            # Evidence from victim district
            if d == v_dist:
                if arch_name in ["LOCAL_RAPID_CASHOUT", "NIGHTTIME_ATM_CASHOUT"]:
                    dist_weights[i] += 4.5
                elif arch_name in ["CROSS_DISTRICT_MULE_CHAIN"]:
                    dist_weights[i] += 0.2
                else:
                    dist_weights[i] += 1.2
            # Evidence from adjacent corridors
            if d in DISTRICT_ADJACENCY[dom_d] or d in DISTRICT_ADJACENCY[t_dist]:
                dist_weights[i] += 1.2

        # Special archetype weighting
        if arch_name == "TRANSPORT_HUB_MOVEMENT":
            for d in ["CENTRAL", "NEW_DELHI", "NORTH", "EAST"]:
                dist_weights[ALL_11_DISTRICTS.index(d)] += 2.5

        # Normalize Stage 1 probabilities
        dist_sum = dist_weights.sum()
        p_district = dist_weights / dist_sum

        # Check Stage 1 normalization tolerance
        d_sum_err = abs(float(p_district.sum()) - 1.0)
        if d_sum_err > self.max_district_sum_error:
            self.max_district_sum_error = d_sum_err
        if (p_district < 0.0).any() or (p_district > 1.0).any() or np.isnan(p_district).any():
            self.invalid_district_prob_rows += 1

        # Sample realized district
        d_idx = self.rng.choice(len(ALL_11_DISTRICTS), p=p_district)
        realized_district = ALL_11_DISTRICTS[d_idx]

        # =========================================================================
        # STAGE 2: SAMPLE CLUSTER INSIDE REALIZED DISTRICT (Strict Invariant)
        # =========================================================================
        cand_clusters_in_district = self.clusters_by_district[realized_district]
        n_cands = len(cand_clusters_in_district)
        cluster_weights = np.ones(n_cands, dtype=np.float64) * 0.25 # Intra-district baseline

        for i, c in enumerate(cand_clusters_in_district):
            cid = c["id"]
            # Commercial role
            if cid in COMMERCIAL_HUB_CLUSTER_IDS and arch_name in ["NEARBY_COMMERCIAL_CORRIDOR", "MULTI_BANK_DISPERSAL"]:
                cluster_weights[i] += 4.0
            # Transport role
            if cid in TRANSPORT_HUB_CLUSTER_IDS and arch_name in ["TRANSPORT_HUB_MOVEMENT", "CROSS_DISTRICT_MULE_CHAIN"]:
                cluster_weights[i] += 4.5
            # ATM density role
            if c["atm_density"] >= 26.0 and arch_name in ["HIGH_VALUE_DELAYED_CASHOUT", "NIGHTTIME_ATM_CASHOUT"]:
                cluster_weights[i] += 3.5
            # Terminal proximity role
            if realized_district == t_dist:
                cluster_weights[i] += 2.0
            # Syndicate corridor role
            if arch_name == "RECURRING_SYNDICATE_CORRIDOR":
                if cid in syn["preferred_clusters"]:
                    cluster_weights[i] += 5.5

        # Normalize Stage 2 probabilities
        clust_sum = cluster_weights.sum()
        p_cluster = cluster_weights / clust_sum

        # Check Stage 2 normalization tolerance
        c_sum_err = abs(float(p_cluster.sum()) - 1.0)
        if c_sum_err > self.max_cluster_sum_error:
            self.max_cluster_sum_error = c_sum_err
        if (p_cluster < 0.0).any() or (p_cluster > 1.0).any() or np.isnan(p_cluster).any():
            self.invalid_cluster_prob_rows += 1

        # Sample realized cluster
        c_choice_idx = self.rng.choice(n_cands, p=p_cluster)
        target_cluster = cand_clusters_in_district[c_choice_idx]
        target_cid = target_cluster["id"]
        target_cluster_name = target_cluster["name"]

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
        syn_family = syn["id"] if arch_name == "RECURRING_SYNDICATE_CORRIDOR" else f"SYN-V61-{(case_num % 100) + 1:03d}"
        mule_family = f"MULE-V61-{(case_num % 150) + 1:03d}"

        return {
            "case_id": f"CMP-V61-{case_num:06d}",
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
            "generator_version": "v6.1"
        }

    def generate_dataset(self) -> pd.DataFrame:
        """Generates the full deterministic 15,000-case dataset."""
        print(f"Generating {self.total_cases} cases with seed {self.seed} (V6.1 Two-Stage Model)...")
        start_date = datetime.datetime(2025, 1, 1, 0, 0, 0)
        raw_offsets = np.sort(self.rng.uniform(0, 365.0 * 86400.0, size=self.total_cases))

        records = []
        for i in range(self.total_cases):
            case_base = start_date + datetime.timedelta(seconds=float(raw_offsets[i]))
            rec = self.generate_case(i + 1, case_base)
            records.append(rec)

        df = pd.DataFrame(records)
        df = df.sort_values("event_timestamp").reset_index(drop=True)
        df["case_id"] = [f"CMP-V61-{k+1:06d}" for k in range(self.total_cases)]

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
    parser = argparse.ArgumentParser(description="Generate Delhi V6.1 Controlled Synthetic Dataset")
    parser.add_argument("--cases", type=int, default=15000, help="Total cases (default: 15000)")
    parser.add_argument("--seed", type=int, default=37184, help="RNG seed (default: 37184)")
    parser.add_argument("--output", type=str, default=None, help="Output path for csv.gz")
    args = parser.parse_args()

    base_dir = os.path.abspath(os.path.join(os.path.dirname(__file__), "..", ".."))
    out_path = args.output or os.path.join(base_dir, "ml", "data", "delhi_v6_1_cases.csv.gz")

    gen = DelhiV61DatasetGenerator(seed=args.seed, total_cases=args.cases)
    df = gen.generate_dataset()
    save_deterministic_csv_gz(df, out_path)
    print(f"Generator Quality Checks: max_dist_sum_err={gen.max_district_sum_error:.2e}, max_clust_sum_err={gen.max_cluster_sum_error:.2e}, mismatches={gen.district_cluster_mismatches}")

if __name__ == "__main__":
    main()
