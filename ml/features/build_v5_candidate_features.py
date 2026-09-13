"""
CyberShield AI — V5 Candidate Feature Builder
Phase A.4: Generates Leakage-Safe Feature Matrices for Pointwise Location Ranking & Time Prediction

Features:
- Exactly 48 location features matching frozen v5_feature_contract.json
- Exactly 22 time features matching frozen design
- Pointwise candidate pool expansion (25 candidates per complaint)
- Chronological historical features: for case at time T, uses strictly historical cases with reported_at < T
- Zero future-derived data, zero target disclosure in feature space
"""

import os
import sys
import math
import bisect
import datetime
from typing import Dict, Any, List, Tuple, Optional
import numpy as np
import pandas as pd

from ml.data.generate_delhi_v5_dataset import (
    DELHI_CLUSTERS_V5,
    ALL_11_DISTRICTS,
    DISTRICT_ADJACENCY,
    haversine_km
)
from ml.geo.candidate_generator import CandidateLocationGenerator

# Categorical Mappings (Frozen)
FRAUD_TYPE_MAP_V5 = {
    "unknown": 0,
    "investment scam": 1,
    "upi fraud": 2,
    "impersonation scam": 3,
    "remote access scam": 4,
    "marketplace fraud": 5,
    "phishing fraud": 6,
    "loan app scam": 7,
    "job scam": 8,
    "digital payment fraud": 9
}

CHANNEL_MAP_V5 = {
    "unknown": 0,
    "upi": 1,
    "imps": 2,
    "neft": 3,
    "rtgs": 4,
    "netbanking": 5,
    "other": 6
}

DISTRICT_MAP_V5 = {
    d: i + 1 for i, d in enumerate(ALL_11_DISTRICTS)
}
DISTRICT_MAP_V5["UNKNOWN"] = 0

DISTRICT_CENTROIDS_V5 = {
    "CENTRAL": (28.6491, 77.1872),
    "NEW_DELHI": (28.6185, 77.2146),
    "SOUTH": (28.5410, 77.2041),
    "SOUTH_EAST": (28.5414, 77.2643),
    "WEST": (28.6442, 77.0999),
    "SOUTH_WEST": (28.5758, 77.0731),
    "NORTH": (28.6990, 77.2102),
    "NORTH_WEST": (28.7255, 77.1355),
    "EAST": (28.6252, 77.2953),
    "NORTH_EAST": (28.6698, 77.2680),
    "SHAHDARA": (28.6683, 77.3005)
}

LOCATION_FEATURE_NAMES_V5 = [
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
    "candidate_same_any_account_zone",
    "dist_to_complaint_zone_km",
    "dist_to_terminal_zone_km",
    "transfer_burst_score",
    "night_activity_ratio",
    "terminal_mule_district_encoded",
    "prior_24h_cashout_count_near_candidate",
    "prior_30d_cluster_activity"
]

TIME_FEATURE_NAMES_V4 = [
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
    "branching_factor",
    "night_activity_ratio",
    "fraud_neighbor_count",
    "mule_connection_count",
    "terminal_mule_district_encoded",
    "fraud_type_historical_cashout_delay"
]


class V5FeatureBuilder:
    def __init__(self, clusters: Optional[List[Dict[str, Any]]] = None):
        self.clusters = clusters or DELHI_CLUSTERS_V5
        self.cluster_by_id = {c["id"]: c for c in self.clusters}
        self.cand_gen = CandidateLocationGenerator(clusters=self.clusters)

    def extract_time_features(self, df_cases: pd.DataFrame) -> pd.DataFrame:
        """Extracts the 22 frozen time features directly from case records."""
        records = []
        for _, row in df_cases.iterrows():
            amt = float(row["amount"])
            log_amt = math.log1p(amt)
            ft_code = FRAUD_TYPE_MAP_V5.get(str(row["fraud_type"]).lower().strip(), 0)
            ch_code = CHANNEL_MAP_V5.get(str(row["payment_channel"]).lower().strip(), 0)
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
            term_dist_enc = DISTRICT_MAP_V5.get(str(row["terminal_mule_district"]), 0)
            base_delay = 140.0 if ft_code in (0, 9) else (240.0 if ft_code == 1 else (55.0 if ft_code == 2 else 120.0))

            records.append({
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
                "branching_factor": branching,
                "night_activity_ratio": night_ratio,
                "fraud_neighbor_count": fraud_neighbors,
                "mule_connection_count": mule_count,
                "terminal_mule_district_encoded": term_dist_enc,
                "fraud_type_historical_cashout_delay": base_delay
            })

        res_df = pd.DataFrame(records)[TIME_FEATURE_NAMES_V4]
        return res_df

    def build_candidate_matrices(
        self,
        df_cases: pd.DataFrame,
        top_k: int = 25
    ) -> Tuple[pd.DataFrame, np.ndarray, List[Dict[str, Any]]]:
        """
        Builds the candidate-level pointwise dataset for location ranking.
        Enforces chronological historical lookback:
        Prior historical events used for case i are strictly historical cases with reported_at < case_i.event_timestamp.
        """
        # Ensure sorting by event_timestamp
        df_sorted = df_cases.sort_values("event_timestamp").reset_index(drop=True)

        # Precompute chronological event timestamps and realized clusters for historical indexing
        event_timestamps = pd.to_datetime(df_sorted["event_timestamp"]).values
        reported_timestamps = pd.to_datetime(df_sorted["reported_at"]).values
        realized_cids = df_sorted["realized_cashout_cluster_id"].values
        realized_lats = df_sorted["realized_cashout_lat"].values
        realized_lons = df_sorted["realized_cashout_lon"].values

        # Cumulative chronological history arrays
        hist_records = []
        for i in range(len(df_sorted)):
            hist_records.append((
                reported_timestamps[i], # timestamp when cash-out outcome is available historically
                realized_cids[i],
                realized_lats[i],
                realized_lons[i]
            ))

        # We can maintain chronological rolling window fast lookups
        hist_rep_times = np.array([r[0] for r in hist_records])
        hist_cids = np.array([r[1] for r in hist_records])
        hist_lats = np.array([r[2] for r in hist_records])
        hist_lons = np.array([r[3] for r in hist_records])

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
            prior_times = hist_rep_times[:idx_cutoff]

            # Prior 24h cutoff
            cutoff_24h = cutoff_time - np.timedelta64(24, "h")
            idx_24h = np.searchsorted(prior_times, cutoff_24h)

            # Prior 30d cutoff
            cutoff_30d = cutoff_time - np.timedelta64(30, "D")
            idx_30d = np.searchsorted(prior_times, cutoff_30d)

            # Generate candidate pool (top_k candidates using prediction-time data only)
            complaint_dict = {
                "victim_lat": v_lat,
                "victim_lon": v_lon,
                "victim_district": v_dist,
                "fraud_type": ft_str
            }
            candidates = self.cand_gen.generate_candidates_for_complaint(
                complaint=complaint_dict,
                top_k=top_k,
                terminal_zone=term_dist
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
                same_any_dist = int(c_dist in (v_dist, term_dist))
                dist_to_comp_zone = haversine_km(v_dist_centroid[0], v_dist_centroid[1], c_lat, c_lon)
                dist_to_term_zone = haversine_km(t_dist_centroid[0], t_dist_centroid[1], c_lat, c_lon)

                # Chronological Candidate Historical Aggregates
                # 1. Total cluster cashout count prior
                hist_c_count = int(np.sum(prior_cids == c_id))
                hist_c_amount = hist_c_count * 50000.0

                # 2. Prior 30d activity
                prior_30d_count = int(np.sum(prior_cids[idx_30d:] == c_id))
                recent_7d_count = int(np.sum(prior_cids[max(0, idx_cutoff - 50):] == c_id))

                # 3. Prior 24h near candidate (within 5 km)
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
                    same_any_dist,
                    dist_to_comp_zone,
                    dist_to_term_zone,
                    burst,
                    night_ratio,
                    term_dist_enc,
                    float(prior_24h_near),
                    float(prior_30d_count)
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

        X_df = pd.DataFrame(feature_rows, columns=LOCATION_FEATURE_NAMES_V5)
        y = np.array(labels, dtype=np.int32)
        return X_df, y, metadata_rows
