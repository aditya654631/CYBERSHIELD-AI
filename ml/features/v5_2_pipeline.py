"""
CyberShield AI — Phase A.4E Canonical V5.2 Pipeline
Unified, single-source-of-truth implementation for:
- 60-cluster universe and ID-index mappings
- Canonical historical fraud-type affinity
- Multi-Source Partitioned Quota Candidate Retrieval (k=25)
- Optional deterministic Multiclass Candidate Rescue (max 1-2 slots, preserving k=25)
- Canonical 54-feature ranking contract (intra-complaint relative ranks)
- Case-level feature contract for direct 60-class classifier
- Canonical candidate recall calculation
"""

import os
import sys
import math
import hashlib
from typing import Dict, Any, List, Tuple, Optional, Set
import numpy as np
import pandas as pd

from ml.data.generate_delhi_v5_dataset import (
    DELHI_CLUSTERS_V5,
    ALL_11_DISTRICTS,
    haversine_km
)

# Canonical 60-cluster mapping to 0..59 indices
CLUSTER_IDS_SORTED: List[int] = sorted([c["id"] for c in DELHI_CLUSTERS_V5])
CID_TO_IDX: Dict[int, int] = {cid: idx for idx, cid in enumerate(CLUSTER_IDS_SORTED)}
IDX_TO_CID: Dict[int, int] = {idx: cid for idx, cid in enumerate(CLUSTER_IDS_SORTED)}

# District mappings
DISTRICT_MAP_V5 = {
    "CENTRAL": 0, "EAST": 1, "NEW_DELHI": 2, "NORTH": 3, "NORTH_EAST": 4,
    "NORTH_WEST": 5, "SHAHDARA": 6, "SOUTH": 7, "SOUTH_EAST": 8, "SOUTH_WEST": 9, "WEST": 10
}

FRAUD_TYPE_MAP_V5 = {
    "digital payment fraud": 0, "impersonation scam": 1, "investment scam": 2,
    "job scam": 3, "loan app scam": 4, "marketplace fraud": 5, "phishing fraud": 6,
    "remote access scam": 7, "upi fraud": 8
}

CHANNEL_MAP_V5 = {
    "upi": 0, "imps": 1, "neft": 2, "rtgs": 3, "card_p2p": 4, "crypto_p2p": 5
}

DISTRICT_ADJACENCY: Dict[str, List[str]] = {
    "CENTRAL": ["NORTH", "NEW_DELHI", "WEST", "NORTH_WEST"],
    "NEW_DELHI": ["CENTRAL", "SOUTH", "SOUTH_WEST", "SOUTH_EAST"],
    "SOUTH": ["NEW_DELHI", "SOUTH_EAST", "SOUTH_WEST"],
    "SOUTH_EAST": ["SOUTH", "NEW_DELHI", "EAST", "SHAHDARA"],
    "WEST": ["CENTRAL", "NORTH_WEST", "SOUTH_WEST"],
    "SOUTH_WEST": ["WEST", "NEW_DELHI", "SOUTH"],
    "NORTH_WEST": ["NORTH", "WEST", "CENTRAL"],
    "NORTH": ["CENTRAL", "NORTH_WEST", "NORTH_EAST"],
    "NORTH_EAST": ["NORTH", "EAST", "SHAHDARA"],
    "EAST": ["NORTH_EAST", "SHAHDARA", "SOUTH_EAST"],
    "SHAHDARA": ["NORTH_EAST", "EAST", "SOUTH_EAST"]
}

TOP_COMMERCIAL_HUB_IDS = [7, 22, 57, 16, 25, 34, 42, 50, 64, 29]

# Canonical 54 ranking features for V5.2
LOCATION_FEATURE_NAMES_V5_2: List[str] = [
    # 1. Base Complaint & Event Features (16)
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
    "transaction_velocity",
    "transfer_burst_score",
    "chain_duration_minutes",
    "average_hop_interval",

    # 2. Graph & Network Features (9)
    "total_transferred",
    "mean_transfer_amount",
    "max_transfer_amount",
    "branching_factor",
    "max_degree",
    "mean_degree",
    "max_pagerank",
    "max_betweenness",
    "connected_component_size",

    # 3. Mule & Neighborhood Features (5)
    "fraud_neighbor_count",
    "mule_connection_count",
    "night_activity_ratio",
    "terminal_mule_district_encoded",
    "prior_7d_similar_fraud_count",

    # 4. Cluster Candidate Static & Historical Features (6)
    "historical_cluster_cashout_count",
    "historical_cluster_cashout_amount",
    "historical_cluster_risk",
    "atm_density",
    "recent_cluster_activity",
    "prior_30d_cluster_activity",

    # 5. Candidate-Case Interaction Features (13)
    "distance_from_victim",
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
    "prior_24h_cashout_count_near_candidate",
    "candidate_corridor_support_score",

    # 6. Intra-Complaint Relative Ranking Features (5)
    "candidate_victim_distance_rank",
    "candidate_terminal_distance_rank",
    "candidate_corridor_support_rank",
    "candidate_atm_density_rank",
    "candidate_fraud_affinity_rank"
]

# Canonical 25 case-level features for direct 60-class multiclass model
MULTICLASS_FEATURE_NAMES_V5_2: List[str] = [
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
    "mule_account_count",
    "distinct_bank_count",
    "victim_lat",
    "victim_lon",
    "victim_district_encoded",
    "terminal_mule_district_encoded",
    "transaction_velocity",
    "transfer_burst_score",
    "graph_depth",
    "graph_branching_factor",
    "night_activity_ratio",
    "chain_duration_minutes",
    "average_hop_interval",
    "dist_origin_to_terminal_mule_district_km",
    "prior_7d_similar_fraud_count"
]


def compute_canonical_fraud_affinity(df_history: pd.DataFrame, top_n: int = 5) -> Dict[str, List[int]]:
    """Single canonical historical fraud-affinity mapping (top N clusters per fraud type)."""
    affinity_map: Dict[str, List[int]] = {}
    if df_history is None or len(df_history) == 0:
        return affinity_map
    for ft, grp in df_history.groupby("fraud_type"):
        top_cids = list(grp["realized_cashout_cluster_id"].value_counts().head(top_n).index)
        affinity_map[ft] = top_cids
    return affinity_map


class V52CandidateGenerator:
    """Canonical Multi-Source Partitioned Quota Candidate Retrieval with optional rescue."""

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
        top_k: int = 25,
        rescue_cluster_ids: Optional[List[int]] = None
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

        # Optional deterministic candidate rescue: replace lowest-priority fallback slots
        if rescue_cluster_ids:
            for r_cid in rescue_cluster_ids:
                if r_cid in self.cluster_by_id and r_cid not in final_ids:
                    final_ids[-1] = r_cid  # displace lowest-priority slot

        return [self.cluster_by_id[cid] for cid in final_ids]


class V52Pipeline:
    """Canonical feature extractor and recall evaluator."""

    def __init__(self, clusters: Optional[List[Dict[str, Any]]] = None):
        self.clusters = clusters or DELHI_CLUSTERS_V5
        self.cluster_by_id = {c["id"]: c for c in self.clusters}
        self.cand_gen = V52CandidateGenerator(clusters=self.clusters)

    def extract_multiclass_features(
        self,
        df_cases: pd.DataFrame,
        historical_cases: Optional[pd.DataFrame] = None
    ) -> Tuple[pd.DataFrame, np.ndarray]:
        """Extracts the 25 case-level features for direct multiclass 60-cluster classification."""
        df_sorted = df_cases.sort_values("event_timestamp").reset_index(drop=True)
        if historical_cases is not None and len(historical_cases) > 0:
            full_hist = pd.concat([historical_cases, df_sorted]).sort_values("event_timestamp").reset_index(drop=True)
        else:
            full_hist = df_sorted

        hist_rep_times = pd.to_datetime(full_hist["reported_at"]).values
        hist_cids = full_hist["realized_cashout_cluster_id"].values
        hist_fts = full_hist["fraud_type"].values

        rows = []
        labels = []
        n_cases = len(df_sorted)

        district_centers = {}
        for d in ALL_11_DISTRICTS:
            d_cls = [c for c in self.clusters if c["district"] == d]
            district_centers[d] = (np.mean([c["lat"] for c in d_cls]), np.mean([c["lon"] for c in d_cls]))

        for i in range(n_cases):
            row = df_sorted.iloc[i]
            amt = float(row["amount"])
            ft_str = str(row["fraud_type"]).lower().strip()
            ch_str = str(row["payment_channel"]).lower().strip()
            v_lat = float(row["victim_lat"])
            v_lon = float(row["victim_lon"])
            v_dist = str(row["victim_district"])
            t_dist = str(row["terminal_mule_district"])
            velocity = float(row["transaction_velocity"])
            chain_dur = max(1.0, float(amt / max(1.0, velocity) * 60.0))
            hop_count = int(row["transaction_hop_count"])
            hop_int = float(chain_dur / max(1, hop_count))

            t_lat, t_lon = district_centers.get(t_dist, (v_lat, v_lon))
            d_to_term = haversine_km(v_lat, v_lon, t_lat, t_lon)

            # Historical 7d context
            curr_rep = np.datetime64(pd.to_datetime(row["reported_at"]))
            t_7d_ago = curr_rep - np.timedelta64(7, "D")
            hist_mask = (hist_rep_times >= t_7d_ago) & (hist_rep_times < curr_rep)
            p7d_count = float(np.sum(hist_mask & (hist_fts == row["fraud_type"])))

            record = {
                "log_amount": math.log1p(amt),
                "fraud_type_encoded": FRAUD_TYPE_MAP_V5.get(ft_str, 0),
                "payment_channel_encoded": CHANNEL_MAP_V5.get(ch_str, 0),
                "complaint_hour": pd.to_datetime(row["reported_at"]).hour,
                "day_of_week": pd.to_datetime(row["reported_at"]).weekday(),
                "weekend_flag": int(pd.to_datetime(row["reported_at"]).weekday() >= 5),
                "night_flag": int(pd.to_datetime(row["reported_at"]).hour >= 22 or pd.to_datetime(row["reported_at"]).hour < 6),
                "complaint_delay_minutes": float(row["reporting_delay_minutes"]),
                "transaction_count": int(row["transaction_count"]),
                "hop_count": hop_count,
                "mule_account_count": int(row["mule_account_count"]),
                "distinct_bank_count": int(row["distinct_bank_count"]),
                "victim_lat": v_lat,
                "victim_lon": v_lon,
                "victim_district_encoded": DISTRICT_MAP_V5.get(v_dist, 0),
                "terminal_mule_district_encoded": DISTRICT_MAP_V5.get(t_dist, 0),
                "transaction_velocity": velocity,
                "transfer_burst_score": float(row["transfer_burst_score"]),
                "graph_depth": int(row["graph_depth"]),
                "graph_branching_factor": float(row["graph_branching_factor"]),
                "night_activity_ratio": float(row["night_activity_ratio"]),
                "chain_duration_minutes": chain_dur,
                "average_hop_interval": hop_int,
                "dist_origin_to_terminal_mule_district_km": d_to_term,
                "prior_7d_similar_fraud_count": p7d_count
            }
            rows.append(record)
            true_cid = int(row["realized_cashout_cluster_id"])
            labels.append(CID_TO_IDX[true_cid])

        X_df = pd.DataFrame(rows)[MULTICLASS_FEATURE_NAMES_V5_2]
        return X_df, np.array(labels, dtype=np.int32)

    def build_ranking_matrices(
        self,
        df_cases: pd.DataFrame,
        top_k: int = 25,
        historical_cases: Optional[pd.DataFrame] = None,
        rescue_clusters_per_case: Optional[List[List[int]]] = None
    ) -> Tuple[pd.DataFrame, np.ndarray, List[Dict[str, Any]]]:
        """Builds canonical 54-feature ranking matrix with deterministic relative ranks."""
        df_sorted = df_cases.sort_values("event_timestamp").reset_index(drop=True)
        if historical_cases is not None and len(historical_cases) > 0:
            full_hist = pd.concat([historical_cases, df_sorted]).sort_values("event_timestamp").reset_index(drop=True)
        else:
            full_hist = df_sorted

        hist_rep_times = pd.to_datetime(full_hist["reported_at"]).values
        hist_cids = full_hist["realized_cashout_cluster_id"].values
        hist_lats = full_hist["realized_cashout_lat"].values
        hist_lons = full_hist["realized_cashout_lon"].values
        hist_fts = full_hist["fraud_type"].values

        fraud_affinity_map = compute_canonical_fraud_affinity(full_hist, top_n=5)

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
            velocity = float(row["transaction_velocity"])
            burst = float(row["transfer_burst_score"])
            chain_dur = max(1.0, float(amt / max(1.0, velocity) * 60.0))
            hop_int = float(chain_dur / max(1, hop_count))
            branching = float(row["graph_branching_factor"])
            night_ratio = float(row["night_activity_ratio"])
            fraud_neighbors = int(row["beneficiary_account_count"])
            term_dist_enc = DISTRICT_MAP_V5.get(term_dist, 0)
            base_delay = 140.0 if ft_code in (0, 9) else (240.0 if ft_code == 1 else (55.0 if ft_code == 2 else 120.0))

            # Retrieve candidates
            rescue_cids = rescue_clusters_per_case[i] if rescue_clusters_per_case else None
            cands = self.cand_gen.generate_candidates(
                victim_lat=v_lat,
                victim_lon=v_lon,
                victim_district=v_dist,
                terminal_district=term_dist,
                fraud_type=row["fraud_type"],
                fraud_affinity_map=fraud_affinity_map,
                top_k=top_k,
                rescue_cluster_ids=rescue_cids
            )

            # Historical lookups strictly prior to current reported_at
            curr_rep = np.datetime64(rep_dt)
            t_24h_ago = curr_rep - np.timedelta64(24, "h")
            t_7d_ago = curr_rep - np.timedelta64(7, "D")
            t_30d_ago = curr_rep - np.timedelta64(30, "D")

            valid_hist = hist_rep_times < curr_rep
            h_times_valid = hist_rep_times[valid_hist]
            h_cids_valid = hist_cids[valid_hist]
            h_lats_valid = hist_lats[valid_hist]
            h_lons_valid = hist_lons[valid_hist]
            h_fts_valid = hist_fts[valid_hist]

            mask_24h = h_times_valid >= t_24h_ago
            mask_7d = h_times_valid >= t_7d_ago
            mask_30d = h_times_valid >= t_30d_ago

            p7d_count = float(np.sum(mask_7d & (h_fts_valid == row["fraud_type"])))

            # Pre-allocate candidate values for relative ranking
            cand_features_for_case = []
            c_dists = []
            c_term_dists = []
            c_corridors = []
            c_atms = []
            c_fraud_affs = []

            for c in cands:
                c_id = c["id"]
                c_lat = float(c["lat"])
                c_lon = float(c["lon"])
                c_dist_v = haversine_km(v_lat, v_lon, c_lat, c_lon)
                c_district = c["district"]

                same_v_dist = int(c_district == v_dist)
                same_t_dist = int(c_district == term_dist)
                is_adj_v = int(c_district in DISTRICT_ADJACENCY.get(v_dist, []))
                is_adj_t = int(c_district in DISTRICT_ADJACENCY.get(term_dist, []))

                corridor_score = 0.0
                if same_t_dist:
                    corridor_score = 1.0
                elif same_v_dist and term_dist == v_dist:
                    corridor_score = 0.85
                elif is_adj_t:
                    corridor_score = 0.65
                elif is_adj_v:
                    corridor_score = 0.40
                elif same_v_dist:
                    corridor_score = 0.25
                else:
                    corridor_score = 0.05

                d_term = haversine_km(v_lat, v_lon, c_lat, c_lon) if same_t_dist else c_dist_v * 1.1

                c_mask_valid = (h_cids_valid == c_id)
                hist_cnt = float(np.sum(c_mask_valid))
                hist_amt = float(np.sum(c_mask_valid)) * 42000.0
                hist_risk = float(c.get("risk", 0.7))
                atm_dens = float(c.get("atm_density", 25.0))
                recent_act = float(np.sum(c_mask_valid & mask_7d))
                prior_30d_act = float(np.sum(c_mask_valid & mask_30d))

                lat_diff = np.abs(h_lats_valid[mask_24h] - c_lat)
                lon_diff = np.abs(h_lons_valid[mask_24h] - c_lon)
                approx_dists = (lat_diff + lon_diff) * 111.0
                p24_near = float(np.sum(approx_dists <= 5.0))

                ft_freq = float(np.sum(c_mask_valid & (h_fts_valid == row["fraud_type"])))

                c_dists.append(c_dist_v)
                c_term_dists.append(d_term)
                c_corridors.append(corridor_score)
                c_atms.append(atm_dens)
                c_fraud_affs.append(ft_freq)

                base_dict = {
                    "log_amount": log_amt,
                    "fraud_type_encoded": ft_code,
                    "payment_channel_encoded": ch_code,
                    "complaint_hour": hour,
                    "day_of_week": dow,
                    "weekend_flag": weekend,
                    "night_flag": night,
                    "complaint_delay_minutes": delay_min,
                    "transaction_count": tx_count,
                    "hop_count": hop_count,
                    "unique_accounts": uniq_acc,
                    "unique_banks": uniq_banks,
                    "transaction_velocity": velocity,
                    "transfer_burst_score": burst,
                    "chain_duration_minutes": chain_dur,
                    "average_hop_interval": hop_int,
                    "total_transferred": amt * 1.15,
                    "mean_transfer_amount": amt / max(1, tx_count),
                    "max_transfer_amount": amt * 0.75,
                    "branching_factor": branching,
                    "max_degree": float(row.get("distinct_bank_count", 2)) * 1.5,
                    "mean_degree": 1.4,
                    "max_pagerank": 0.08,
                    "max_betweenness": 0.12,
                    "connected_component_size": mule_count + 2,
                    "fraud_neighbor_count": fraud_neighbors,
                    "mule_connection_count": mule_count,
                    "night_activity_ratio": night_ratio,
                    "terminal_mule_district_encoded": term_dist_enc,
                    "prior_7d_similar_fraud_count": p7d_count,
                    "historical_cluster_cashout_count": hist_cnt,
                    "historical_cluster_cashout_amount": hist_amt,
                    "historical_cluster_risk": hist_risk,
                    "atm_density": atm_dens,
                    "recent_cluster_activity": recent_act,
                    "prior_30d_cluster_activity": prior_30d_act,
                    "distance_from_victim": c_dist_v,
                    "fraud_type_cluster_frequency": ft_freq,
                    "transaction_hour": max(0, hour - 1),
                    "time_since_first_transfer": delay_min + 30.0,
                    "time_since_last_transfer": delay_min,
                    "fraud_type_historical_cashout_delay": base_delay,
                    "account_historical_cashout_delay": base_delay * 0.9,
                    "candidate_same_complaint_zone": same_v_dist,
                    "candidate_same_terminal_zone": same_t_dist,
                    "dist_to_complaint_zone_km": c_dist_v if same_v_dist else c_dist_v * 1.3,
                    "dist_to_terminal_zone_km": d_term,
                    "prior_24h_cashout_count_near_candidate": p24_near,
                    "candidate_corridor_support_score": corridor_score
                }
                cand_features_for_case.append(base_dict)
                is_target = int(c_id == true_cid)
                labels.append(is_target)
                metadata_rows.append({
                    "case_id": case_id,
                    "candidate_cluster_id": c_id,
                    "is_target": is_target
                })

            # Compute deterministic intra-complaint relative ranks (tie-break by cluster_id)
            cids_list = [c["id"] for c in cands]

            # Ascending rank for distances (tie-break by cid ascending)
            dist_order = sorted(range(len(cands)), key=lambda idx: (c_dists[idx], cids_list[idx]))
            rank_dist = {dist_order[r]: r + 1 for r in range(len(cands))}

            term_order = sorted(range(len(cands)), key=lambda idx: (c_term_dists[idx], cids_list[idx]))
            rank_term = {term_order[r]: r + 1 for r in range(len(cands))}

            # Descending rank for support, atm, fraud aff (tie-break by cid ascending)
            corr_order = sorted(range(len(cands)), key=lambda idx: (-c_corridors[idx], cids_list[idx]))
            rank_corr = {corr_order[r]: r + 1 for r in range(len(cands))}

            atm_order = sorted(range(len(cands)), key=lambda idx: (-c_atms[idx], cids_list[idx]))
            rank_atm = {atm_order[r]: r + 1 for r in range(len(cands))}

            aff_order = sorted(range(len(cands)), key=lambda idx: (-c_fraud_affs[idx], cids_list[idx]))
            rank_aff = {aff_order[r]: r + 1 for r in range(len(cands))}

            for idx in range(len(cands)):
                cf = cand_features_for_case[idx]
                cf["candidate_victim_distance_rank"] = float(rank_dist[idx])
                cf["candidate_terminal_distance_rank"] = float(rank_term[idx])
                cf["candidate_corridor_support_rank"] = float(rank_corr[idx])
                cf["candidate_atm_density_rank"] = float(rank_atm[idx])
                cf["candidate_fraud_affinity_rank"] = float(rank_aff[idx])
                feature_rows.append(cf)

        X_df = pd.DataFrame(feature_rows)[LOCATION_FEATURE_NAMES_V5_2]
        return X_df, np.array(labels, dtype=np.int32), metadata_rows

    def evaluate_candidate_recall(
        self,
        df_cases: pd.DataFrame,
        historical_cases: Optional[pd.DataFrame] = None,
        cutoffs: List[int] = [10, 15, 20, 25, 30, 60],
        rescue_clusters_per_case: Optional[List[List[int]]] = None
    ) -> Dict[int, float]:
        """Canonical candidate recall evaluation across standardized cutoffs."""
        df_sorted = df_cases.sort_values("event_timestamp").reset_index(drop=True)
        if historical_cases is not None and len(historical_cases) > 0:
            full_hist = pd.concat([historical_cases, df_sorted]).sort_values("event_timestamp").reset_index(drop=True)
        else:
            full_hist = df_sorted

        fraud_affinity_map = compute_canonical_fraud_affinity(full_hist, top_n=5)
        n_cases = len(df_sorted)
        recalls = {k: 0 for k in cutoffs}

        for i in range(n_cases):
            row = df_sorted.iloc[i]
            true_cid = row["realized_cashout_cluster_id"]
            rescue_cids = rescue_clusters_per_case[i] if rescue_clusters_per_case else None
            cands = self.cand_gen.generate_candidates(
                victim_lat=float(row["victim_lat"]),
                victim_lon=float(row["victim_lon"]),
                victim_district=str(row["victim_district"]),
                terminal_district=str(row["terminal_mule_district"]),
                fraud_type=str(row["fraud_type"]),
                fraud_affinity_map=fraud_affinity_map,
                top_k=max(cutoffs),
                rescue_cluster_ids=rescue_cids
            )
            cand_cids = [c["id"] for c in cands]
            for k in cutoffs:
                if true_cid in cand_cids[:k]:
                    recalls[k] += 1

        return {k: round(v / n_cases * 100, 2) for k, v in recalls.items()}
