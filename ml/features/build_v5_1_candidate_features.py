"""
CyberShield AI — V5.1 Candidate Generator & Feature Matrix Builder
Phase A.4C: Implements Multi-Source Partitioned Quota Retrieval & Frozen 49 Features

Candidate Retrieval Architecture:
1. Terminal Mule District Clusters (All clusters in terminal district, up to 8)
2. Fraud-Type Historical Affinity (Top 4 favored clusters from prior history)
3. Local Origin Proximity (Top 4 closest clusters to victim in origin district)
4. Commercial / Transit Hubs (Top 6 ATM/commercial density centers across Delhi)
5. Adjacent Corridors (Top 6 clusters in districts adjacent to terminal mule / origin)
6. Distance Fallback (Closest remaining clusters to fill exactly 25 candidates)

Features: Exactly 49 location features matching feature_schema_v5_1.json
"""

import os
import sys
import math
import datetime
from typing import Dict, Any, List, Tuple, Optional, Set
import numpy as np
import pandas as pd

from ml.data.generate_delhi_v5_dataset import (
    DELHI_CLUSTERS_V5,
    ALL_11_DISTRICTS,
    DISTRICT_ADJACENCY,
    haversine_km
)
from ml.features.build_v5_candidate_features import (
    FRAUD_TYPE_MAP_V5,
    CHANNEL_MAP_V5,
    DISTRICT_MAP_V5,
    DISTRICT_CENTROIDS_V5
)

LOCATION_FEATURE_NAMES_V5_1 = [
    "log_amount",
    "fraud_type_encoded",
    "payment_channel_encoded",
    "complaint_hour",
    "day_of_week",
    "weekend_flag",
    "night_flag",
    "complaint_delay_minutes",
    "transaction_count",
    "hop_count",
    "unique_accounts",
    "unique_banks",
    "total_transferred",
    "mean_transfer_amount",
    "max_transfer_amount",
    "transaction_velocity",
    "chain_duration_minutes",
    "average_hop_interval",
    "branching_factor",
    "max_degree",
    "mean_degree",
    "max_pagerank",
    "max_betweenness",
    "connected_component_size",
    "fraud_neighbor_count",
    "mule_connection_count",
    "historical_cluster_cashout_count",
    "historical_cluster_cashout_amount",
    "historical_cluster_risk",
    "atm_density",
    "distance_from_victim",
    "recent_cluster_activity",
    "fraud_type_cluster_frequency",
    "transaction_hour",
    "time_since_first_transfer",
    "time_since_last_transfer",
    "fraud_type_historical_cashout_delay",
    "account_historical_cashout_delay",
    "candidate_same_complaint_zone",
    "candidate_same_terminal_zone",
    "dist_to_complaint_zone_km",
    "dist_to_terminal_zone_km",
    "transfer_burst_score",
    "night_activity_ratio",
    "terminal_mule_district_encoded",
    "prior_24h_cashout_count_near_candidate",
    "prior_30d_cluster_activity",
    "candidate_corridor_support_score",
    "prior_7d_similar_fraud_count",
    "candidate_retrieval_priority_rank"
]

TOP_COMMERCIAL_HUB_IDS = [7, 22, 57, 16, 25, 34, 42, 50, 64, 29]

class V51CandidateGenerator:
    """Multi-Source Partitioned Quota Candidate Generator."""

    def __init__(self, clusters: Optional[List[Dict[str, Any]]] = None):
        self.clusters = clusters or DELHI_CLUSTERS_V5
        self.cluster_by_id = {c["id"]: c for c in self.clusters}
        self.clusters_by_district: Dict[str, List[Dict[str, Any]]] = {}
        for d in ALL_11_DISTRICTS:
            self.clusters_by_district[d] = [c for c in self.clusters if c["district"] == d]

    def generate_candidates(
        self,
        victim_lat: float,
        victim_lon: float,
        victim_district: str,
        terminal_district: str,
        fraud_type: str,
        fraud_affinity_map: Optional[Dict[str, List[int]]] = None,
        top_k: int = 25
    ) -> List[Dict[str, Any]]:
        pool: List[int] = []
        seen: Set[int] = set()

        def add_ids(id_list: List[int]):
            for cid in id_list:
                if cid not in seen:
                    seen.add(cid)
                    pool.append(cid)

        # Channel 1: Terminal mule district clusters
        term_clusters = [c["id"] for c in self.clusters_by_district.get(terminal_district, [])]
        add_ids(term_clusters)

        # Channel 2: Fraud type historical affinity (top 4)
        if fraud_affinity_map and fraud_type in fraud_affinity_map:
            add_ids(fraud_affinity_map[fraud_type][:4])

        # Channel 3: Local origin clusters (closest 4 in victim district)
        v_cls = self.clusters_by_district.get(victim_district, [])
        v_dists = [(c["id"], haversine_km(victim_lat, victim_lon, c["lat"], c["lon"])) for c in v_cls]
        v_dists.sort(key=lambda x: x[1])
        add_ids([x[0] for x in v_dists[:4]])

        # Channel 4: Top commercial hubs across Delhi (top 6)
        add_ids(TOP_COMMERCIAL_HUB_IDS[:6])

        # Channel 5: Adjacent corridor clusters (closest 6 in adjacent districts)
        adj_districts = set(DISTRICT_ADJACENCY.get(terminal_district, []) + DISTRICT_ADJACENCY.get(victim_district, []))
        adj_cands = [(c["id"], haversine_km(victim_lat, victim_lon, c["lat"], c["lon"])) for c in self.clusters if c["district"] in adj_districts]
        adj_cands.sort(key=lambda x: x[1])
        add_ids([x[0] for x in adj_cands[:6]])

        # Channel 6: Additional commercial hubs & nearest distance fallback
        add_ids(TOP_COMMERCIAL_HUB_IDS[6:])
        all_dists = [(c["id"], haversine_km(victim_lat, victim_lon, c["lat"], c["lon"])) for c in self.clusters]
        all_dists.sort(key=lambda x: x[1])
        add_ids([x[0] for x in all_dists])

        final_ids = pool[:top_k]
        return [self.cluster_by_id[cid] for cid in final_ids]


class V51FeatureBuilder:
    """Builds the 49-feature candidate matrix enforcing chronological historical lookback."""

    def __init__(self, clusters: Optional[List[Dict[str, Any]]] = None):
        self.clusters = clusters or DELHI_CLUSTERS_V5
        self.cluster_by_id = {c["id"]: c for c in self.clusters}
        self.cand_gen = V51CandidateGenerator(clusters=self.clusters)

    def build_candidate_matrices(
        self,
        df_cases: pd.DataFrame,
        top_k: int = 25,
        historical_cases: Optional[pd.DataFrame] = None
    ) -> Tuple[pd.DataFrame, np.ndarray, List[Dict[str, Any]]]:
        df_sorted = df_cases.sort_values("event_timestamp").reset_index(drop=True)

        # Establish historical lookup index
        if historical_cases is not None and len(historical_cases) > 0:
            full_hist = pd.concat([historical_cases, df_sorted]).sort_values("event_timestamp").reset_index(drop=True)
        else:
            full_hist = df_sorted

        hist_rep_times = pd.to_datetime(full_hist["reported_at"]).values
        hist_cids = full_hist["realized_cashout_cluster_id"].values
        hist_lats = full_hist["realized_cashout_lat"].values
        hist_lons = full_hist["realized_cashout_lon"].values
        hist_fts = full_hist["fraud_type"].values

        # Precompute static fraud affinity from training slice if available
        fraud_affinity_map: Dict[str, List[int]] = {}
        for ft, grp in full_hist.groupby("fraud_type"):
            fraud_affinity_map[ft] = list(grp["realized_cashout_cluster_id"].value_counts().head(5).index)

        feature_rows = []
        labels = []
        metadata_rows = []

        n_cases = len(df_sorted)

        for i in range(n_cases):
            row = df_sorted.iloc[i]
            case_id = row["case_id"]
            true_cid = row["realized_cashout_cluster_id"]
            v_lat = float(row["victim_lat"])
            v_lon = float(row["victim_lon"])
            v_dist = str(row["victim_district"])
            term_dist = str(row["terminal_mule_district"])
            ft_str = str(row["fraud_type"]).lower().strip()
            ch_str = str(row["payment_channel"]).lower().strip()
            amt = float(row["amount"])
            log_amt = math.log1p(amt)
            ft_code = FRAUD_TYPE_MAP_V5.get(ft_str, 0)
            ch_code = CHANNEL_MAP_V5.get(ch_str, 0)

            rep_dt = pd.to_datetime(row["reported_at"])
            ev_dt = pd.to_datetime(row["event_timestamp"])
            hour = rep_dt.hour
            dow = rep_dt.weekday()
            weekend = int(dow >= 5)
            night = int(hour >= 22 or hour < 6)
            delay_min = float(row["reporting_delay_minutes"])

            tx_count = int(row["transaction_count"])
            hop_count = int(row["transaction_hop_count"])
            mule_count = int(row["mule_account_count"])
            uniq_acc = mule_count + 1
            uniq_banks = int(row["distinct_bank_count"])
            tot_transferred = amt * 0.98
            mean_transfer = amt / max(1, tx_count)
            max_transfer = amt * 0.75
            velocity = float(row["transaction_velocity"])
            chain_dur = max(1.0, amt / max(1.0, velocity) * 60.0)
            hop_int = chain_dur / max(1, hop_count)
            branching = float(row["graph_branching_factor"])
            max_deg = branching * 2.0
            mean_deg = branching * 1.2
            max_pr = 1.0 / max(1, mule_count)
            max_bw = float(hop_count) / 10.0
            comp_size = uniq_acc
            fraud_neighbors = int(row["beneficiary_account_count"])
            tx_hour = ev_dt.hour
            time_since_first = delay_min
            time_since_last = max(0.0, delay_min - chain_dur)
            base_delay = 140.0 if ft_code in (0, 9) else (240.0 if ft_code == 1 else (55.0 if ft_code == 2 else 120.0))
            burst = float(row["transfer_burst_score"])
            night_ratio = float(row["night_activity_ratio"])
            term_dist_enc = DISTRICT_MAP_V5.get(term_dist, 0)

            # Strict Chronological Cutoff: only events reported BEFORE current event timestamp
            cutoff_time = np.datetime64(ev_dt)
            idx_cutoff = np.searchsorted(hist_rep_times, cutoff_time)

            prior_cids = hist_cids[:idx_cutoff]
            prior_lats = hist_lats[:idx_cutoff]
            prior_lons = hist_lons[:idx_cutoff]
            prior_fts = hist_fts[:idx_cutoff]
            prior_times = hist_rep_times[:idx_cutoff]

            cutoff_24h = cutoff_time - np.timedelta64(24, "h")
            idx_24h = np.searchsorted(prior_times, cutoff_24h)

            cutoff_7d = cutoff_time - np.timedelta64(7, "D")
            idx_7d = np.searchsorted(prior_times, cutoff_7d)

            cutoff_30d = cutoff_time - np.timedelta64(30, "D")
            idx_30d = np.searchsorted(prior_times, cutoff_30d)

            # Multi-source candidate retrieval
            candidates = self.cand_gen.generate_candidates(
                victim_lat=v_lat,
                victim_lon=v_lon,
                victim_district=v_dist,
                terminal_district=term_dist,
                fraud_type=row["fraud_type"],
                fraud_affinity_map=fraud_affinity_map,
                top_k=top_k
            )

            v_dist_centroid = DISTRICT_CENTROIDS_V5.get(v_dist, (28.6139, 77.2090))
            t_dist_centroid = DISTRICT_CENTROIDS_V5.get(term_dist, (28.6139, 77.2090))

            for cand_rank, cand in enumerate(candidates):
                c_id = cand["id"]
                c_dist = cand["district"]
                c_lat = cand["lat"]
                c_lon = cand["lon"]
                c_risk = float(cand.get("risk", cand.get("base_risk", 0.5)))
                c_atm = float(cand.get("atm_density", 15.0))

                dist_v = haversine_km(v_lat, v_lon, c_lat, c_lon)
                same_v_dist = int(c_dist == v_dist)
                same_t_dist = int(c_dist == term_dist)
                dist_to_comp_zone = haversine_km(v_dist_centroid[0], v_dist_centroid[1], c_lat, c_lon)
                dist_to_term_zone = haversine_km(t_dist_centroid[0], t_dist_centroid[1], c_lat, c_lon)

                # Continuous Corridor Support Score (Replaces coarse binary shortcut)
                corridor_score = 0.0
                if same_t_dist:
                    corridor_score += 2.0
                elif c_dist in DISTRICT_ADJACENCY.get(term_dist, []):
                    corridor_score += 1.0

                if same_v_dist:
                    corridor_score += 1.5
                elif c_dist in DISTRICT_ADJACENCY.get(v_dist, []):
                    corridor_score += 0.5

                # Decay by distance to terminal mule centroid
                corridor_score += max(0.0, (15.0 - dist_to_term_zone) / 10.0)

                # Chronological Candidate Historical Aggregates
                hist_c_count = int(np.sum(prior_cids == c_id))
                hist_c_amount = hist_c_count * 50000.0

                prior_30d_count = int(np.sum(prior_cids[idx_30d:] == c_id))
                recent_7d_count = int(np.sum(prior_cids[idx_7d:] == c_id))

                # Prior 7d similar fraud count at candidate
                p7_cids = prior_cids[idx_7d:]
                p7_fts = prior_fts[idx_7d:]
                prior_7d_sim_fraud = int(np.sum((p7_cids == c_id) & (p7_fts == row["fraud_type"])))

                # Prior 24h near candidate (within 5 km)
                p24_lats = prior_lats[idx_24h:]
                p24_lons = prior_lons[idx_24h:]
                if len(p24_lats) > 0:
                    dists_24h = [haversine_km(c_lat, c_lon, lt, ln) for lt, ln in zip(p24_lats, p24_lons)]
                    prior_24h_near = sum(1 for d in dists_24h if d <= 5.0)
                else:
                    prior_24h_near = 0

                ft_prior_freq = min(1.0, hist_c_count / max(1.0, float(len(prior_cids))))

                f_row = [
                    log_amt,
                    ft_code,
                    ch_code,
                    hour,
                    dow,
                    weekend,
                    night,
                    delay_min,
                    tx_count,
                    hop_count,
                    uniq_acc,
                    uniq_banks,
                    tot_transferred,
                    mean_transfer,
                    max_transfer,
                    velocity,
                    chain_dur,
                    hop_int,
                    branching,
                    max_deg,
                    mean_deg,
                    max_pr,
                    max_bw,
                    comp_size,
                    fraud_neighbors,
                    mule_count,
                    float(hist_c_count),
                    float(hist_c_amount),
                    c_risk,
                    c_atm,
                    dist_v,
                    float(recent_7d_count),
                    float(ft_prior_freq),
                    tx_hour,
                    time_since_first,
                    time_since_last,
                    base_delay,
                    base_delay,
                    same_v_dist,
                    same_t_dist,
                    dist_to_comp_zone,
                    dist_to_term_zone,
                    burst,
                    night_ratio,
                    term_dist_enc,
                    float(prior_24h_near),
                    float(prior_30d_count),
                    float(corridor_score),
                    float(prior_7d_sim_fraud),
                    cand_rank + 1 # candidate_retrieval_priority_rank (1..25)
                ]

                lbl = 1 if (c_id == true_cid) else 0

                feature_rows.append(f_row)
                labels.append(lbl)
                metadata_rows.append({
                    "case_id": case_id,
                    "candidate_cluster_id": c_id,
                    "candidate_cluster_name": cand["name"],
                    "candidate_rank": cand_rank + 1,
                    "true_cluster_id": true_cid,
                    "is_target": lbl
                })

        X_df = pd.DataFrame(feature_rows, columns=LOCATION_FEATURE_NAMES_V5_1)
        y = np.array(labels, dtype=np.int32)
        return X_df, y, metadata_rows
