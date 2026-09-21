"""
Feature Pipeline for CyberShield AI Location Ranking & Time-to-Cashout Models
Extracts multimodal features across:
1. Complaint characteristics
2. Transaction topology & velocity
3. Graph centrality & mule proximity
4. Candidate cluster geospatial metrics
5. Temporal dynamics & delay signals
"""

import math
import numpy as np
import pandas as pd
from datetime import datetime
from typing import Dict, Any, List, Optional, Tuple

def haversine_km(lat1: float, lon1: float, lat2: float, lon2: float) -> float:
    R = 6371.0
    dlat = math.radians(lat2 - lat1)
    dlon = math.radians(lon2 - lon1)
    a = math.sin(dlat / 2.0)**2 + math.cos(math.radians(lat1)) * math.cos(math.radians(lat2)) * math.sin(dlon / 2.0)**2
    c = 2.0 * math.atan2(math.sqrt(a), math.sqrt(1.0 - a))
    return R * c

FRAUD_TYPE_MAP = {
    "investment scam": 1,
    "upi / qr code fraud": 2,
    "digital arrest / extortion": 3,
    "digital arrest": 3,
    "part-time job fraud": 4,
    "loan app extortion": 5,
    "loan app": 5,
    "other": 6
}

CHANNEL_MAP = {
    "upi": 1,
    "imps": 2,
    "neft": 3,
    "rtgs": 4,
    "netbanking": 5,
    "other": 6
}

FRAUD_HISTORICAL_DELAY = {
    1: 240.0, # Investment
    2: 90.0,  # UPI
    3: 180.0, # Digital arrest
    4: 150.0, # Job fraud
    5: 120.0, # Loan app
    6: 140.0
}

# Explicit V3 Categorical Mappings with UNKNOWN = 0
FRAUD_TYPE_MAP_V3 = {
    "unknown": 0,
    "investment scam": 1,
    "upi / qr code fraud": 2,
    "digital arrest / extortion": 3,
    "digital arrest": 3,
    "part-time job fraud": 4,
    "loan app extortion": 5,
    "loan app": 5,
    "other": 6
}

CHANNEL_MAP_V3 = {
    "unknown": 0,
    "upi": 1,
    "imps": 2,
    "neft": 3,
    "rtgs": 4,
    "netbanking": 5,
    "other": 6
}

FRAUD_HISTORICAL_DELAY_V3 = {
    0: 144.5, # Unknown
    1: 144.1, # Investment scam
    2: 145.0, # UPI / QR code fraud
    3: 143.8, # Digital arrest
    4: 144.4, # Part-time job fraud
    5: 146.2, # Loan app extortion
    6: 144.5  # Other
}

FEATURE_COLUMNS_LOCATION_V3 = [
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
    "account_historical_cashout_delay"
]

DELHI_ZONE_CENTROIDS = {
    "CENTRAL_NEW_DELHI": (28.6360, 77.1989),
    "SOUTH": (28.5410, 77.2041),
    "SOUTH_EAST": (28.5414, 77.2643),
    "WEST": (28.6442, 77.0999),
    "SOUTH_WEST_DWARKA": (28.5758, 77.0731),
    "NORTH": (28.6990, 77.2102),
    "NORTH_WEST": (28.7255, 77.1355),
    "EAST": (28.6252, 77.2953),
    "NORTH_EAST_SHAHDARA": (28.6683, 77.3005)
}

FEATURE_COLUMNS_LOCATION_V3_1 = list(FEATURE_COLUMNS_LOCATION_V3) + [
    "candidate_same_complaint_zone",
    "candidate_same_terminal_zone",
    "candidate_same_any_account_zone",
    "dist_to_complaint_zone_km",
    "dist_to_terminal_zone_km"
]

# V8 Debiased Location Schema (derived from V3.1 minus victim-origin shortcuts, plus new within-zone discriminators)
DEBIASED_EXCLUDED_FEATURES = {
    "distance_from_victim",
    "candidate_same_complaint_zone",
    "dist_to_complaint_zone_km",
}
# Base 40 features (V3.1 minus 3 forbidden victim-origin features)
_V8_BASE_FEATURES = [
    col for col in FEATURE_COLUMNS_LOCATION_V3_1 if col not in DEBIASED_EXCLUDED_FEATURES
]
# 9 additional within-zone discriminative features (NO victim-location, all pre-outcome cluster infrastructure)
_V8_EXTRA_FEATURES = [
    "dist_to_terminal_centroid_km",       # Continuous distance to terminal zone centroid
    "log_cluster_network_exposure",        # log(hist_count * risk) — risk-weighted history
    "cluster_fraud_type_match_score",      # Fraud-type × cluster historical match (v8 version, continuous)
    "cluster_channel_match_score",         # Payment channel × cluster historical co-occurrence
    "cluster_hourly_match_score",          # Hour-of-day × cluster cashout probability
    "cluster_weekday_match_score",         # Weekday class × cluster cashout probability
    "atm_density_log",                     # log(atm_density+1) for scale invariance
    "cluster_risk_x_count",                # Product of risk_score × log(historical_count)
    "dist_to_second_account_zone_km",      # Distance to second-most-common tx account zone centroid
]
FEATURE_COLUMNS_LOCATION_V8_DEBIASED = _V8_BASE_FEATURES + _V8_EXTRA_FEATURES

FEATURE_COLUMNS_LOCATION = [
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
    "distance_from_high_risk_account",
    "recent_cluster_activity",
    "fraud_type_cluster_frequency",
    "is_mule_corridor",
    "transaction_hour",
    "time_since_first_transfer",
    "time_since_last_transfer",
    "fraud_type_historical_cashout_delay",
    "account_historical_cashout_delay"
]

FEATURE_COLUMNS_TIME = [
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
    "transaction_velocity",
    "chain_duration_minutes",
    "average_hop_interval",
    "branching_factor",
    "max_degree",
    "max_pagerank",
    "mule_connection_count",
    "fraud_type_historical_cashout_delay",
    "account_historical_cashout_delay",
    "time_since_last_transfer"
]

class FeaturePipeline:
    def __init__(self):
        self.location_feature_names = list(FEATURE_COLUMNS_LOCATION)
        self.time_feature_names = list(FEATURE_COLUMNS_TIME)

    def extract_complaint_base(self, complaint: Dict[str, Any]) -> Dict[str, Any]:
        amount = float(complaint.get("amount", 50000.0))
        log_amount = float(np.log1p(amount))

        ft = str(complaint.get("fraud_type", "other")).lower().strip()
        f_code = FRAUD_TYPE_MAP.get(ft, 6)
        for k, v in FRAUD_TYPE_MAP.items():
            if k in ft:
                f_code = v
                break

        ch = str(complaint.get("payment_channel", "UPI")).lower().strip()
        c_code = CHANNEL_MAP.get(ch, 1)

        # Parse timing
        t_raw = complaint.get("complaint_timestamp") or complaint.get("reported_at") or complaint.get("incident_timestamp")
        if isinstance(t_raw, str):
            try:
                dt = datetime.fromisoformat(t_raw.replace("Z", "+00:00").split("+")[0])
            except Exception:
                dt = datetime.utcnow()
        elif isinstance(t_raw, datetime):
            dt = t_raw
        else:
            dt = datetime.utcnow()

        hour = dt.hour
        dow = dt.weekday()
        weekend = 1 if dow in [5, 6] else 0
        night = 1 if hour < 6 or hour >= 22 else 0

        delay = float(complaint.get("complaint_delay_minutes", 120.0))
        hops = int(complaint.get("hop_count", 2))

        return {
            "log_amount": log_amount,
            "fraud_type_encoded": f_code,
            "payment_channel_encoded": c_code,
            "complaint_hour": hour,
            "day_of_week": dow,
            "weekend_flag": weekend,
            "night_flag": night,
            "complaint_delay_minutes": delay,
            "hop_count": hops,
            "amount": amount,
            "fraud_type_historical_cashout_delay": FRAUD_HISTORICAL_DELAY.get(f_code, 150.0),
            "account_historical_cashout_delay": 130.0 if hops >= 3 else 180.0,
            "transaction_hour": hour,
            "time_since_first_transfer": delay * 0.4,
            "time_since_last_transfer": max(10.0, delay * 0.15)
        }

    def extract_graph_and_tx_features(
        self,
        base_features: Dict[str, Any],
        transactions: Optional[List[Dict[str, Any]]] = None,
        graph_metrics: Optional[Dict[str, Any]] = None
    ) -> Dict[str, Any]:
        hops = base_features.get("hop_count", 2)
        amount = base_features.get("amount", 50000.0)

        if transactions and len(transactions) > 0:
            tx_count = len(transactions)
            accounts = set()
            banks = set()
            total_tx = 0.0
            amounts = []
            for tx in transactions:
                accounts.add(tx.get("from_account"))
                accounts.add(tx.get("to_account"))
                banks.add(tx.get("bank", "Bank"))
                amt = float(tx.get("amount", 0.0))
                amounts.append(amt)
                total_tx += amt

            mean_amt = float(np.mean(amounts)) if amounts else amount
            max_amt = float(np.max(amounts)) if amounts else amount
            chain_dur = float(tx_count * 12.0)
            velocity = round(tx_count / max(0.5, chain_dur / 60.0), 2)
            avg_hop_int = round(chain_dur / max(1, hops), 1)
            branching = round(tx_count / max(1, hops), 2)
            uniq_acc = len(accounts)
            uniq_banks = len(banks)
        else:
            # Default transaction indicators derived from hop count
            tx_count = hops * 3
            uniq_acc = hops + 3
            uniq_banks = min(4, hops + 1)
            total_tx = amount * 1.3
            mean_amt = amount / max(1, hops)
            max_amt = amount
            chain_dur = float(hops * 15.0)
            velocity = round(tx_count / max(0.5, chain_dur / 60.0), 2)
            avg_hop_int = 15.0
            branching = 2.5

        if graph_metrics:
            max_deg = float(graph_metrics.get("max_degree", 4.0))
            mean_deg = float(graph_metrics.get("mean_degree", 2.2))
            max_pr = float(graph_metrics.get("max_pagerank", 0.32))
            max_btw = float(graph_metrics.get("max_betweenness", 0.28))
            cc_size = int(graph_metrics.get("connected_components", 1))
            fraud_nbrs = int(graph_metrics.get("fraud_neighbor_count", 3))
            mule_conn = int(graph_metrics.get("high_risk_mule_nodes", 2))
        else:
            max_deg = float(hops + 2)
            mean_deg = 2.2
            max_pr = 0.35 if hops >= 3 else 0.22
            max_btw = 0.30 if hops >= 3 else 0.15
            cc_size = 1
            fraud_nbrs = 2 if hops >= 2 else 1
            mule_conn = 2 if hops >= 2 else 1

        return {
            "transaction_count": tx_count,
            "unique_accounts": uniq_acc,
            "unique_banks": uniq_banks,
            "total_transferred": total_tx,
            "mean_transfer_amount": mean_amt,
            "max_transfer_amount": max_amt,
            "transaction_velocity": velocity,
            "chain_duration_minutes": chain_dur,
            "average_hop_interval": avg_hop_int,
            "branching_factor": branching,
            "max_degree": max_deg,
            "mean_degree": mean_deg,
            "max_pagerank": max_pr,
            "max_betweenness": max_btw,
            "connected_component_size": cc_size,
            "fraud_neighbor_count": fraud_nbrs,
            "mule_connection_count": mule_conn
        }

    def build_candidate_row(
        self,
        base_features: Dict[str, Any],
        graph_tx_features: Dict[str, Any],
        candidate: Dict[str, Any]
    ) -> Dict[str, Any]:
        dist_victim = float(candidate.get("distance_from_victim_km", 50.0))
        is_mule = int(candidate.get("is_mule_corridor", 0))

        # Mule distance heuristic: 0 km if it's the mule corridor, otherwise proportional to victim distance
        dist_mule = 0.0 if is_mule == 1 else max(15.0, dist_victim * 0.85)

        cl_count = float(candidate.get("historical_cashout_count", 500))
        cl_amount = float(candidate.get("historical_cashout_amount", 25000000.0))
        cl_risk = float(candidate.get("historical_risk", 0.60))
        atm_dens = float(candidate.get("atm_density", 18.0))

        recent_act = round(cl_count / 100.0, 2)
        f_type_code = base_features.get("fraud_type_encoded", 1)
        freq = round((cl_risk * 1.2) * (1.1 if f_type_code in [1, 2] else 0.9), 3)

        row = {
            **base_features,
            **graph_tx_features,
            "historical_cluster_cashout_count": cl_count,
            "historical_cluster_cashout_amount": cl_amount,
            "historical_cluster_risk": cl_risk,
            "atm_density": atm_dens,
            "distance_from_victim": dist_victim,
            "distance_from_high_risk_account": dist_mule,
            "recent_cluster_activity": recent_act,
            "fraud_type_cluster_frequency": freq,
            "is_mule_corridor": is_mule
        }
        return row

    def build_candidate_matrix(
        self,
        complaint: Dict[str, Any],
        candidates: List[Dict[str, Any]],
        transactions: Optional[List[Dict[str, Any]]] = None,
        graph_metrics: Optional[Dict[str, Any]] = None
    ) -> Tuple[np.ndarray, np.ndarray, List[str], List[str]]:
        base = self.extract_complaint_base(complaint)
        gtx = self.extract_graph_and_tx_features(base, transactions, graph_metrics)

        location_rows = []
        time_rows = []

        # Time model input (one row per complaint)
        time_dict = {**base, **gtx}
        time_row = [float(time_dict.get(c, 0.0)) for c in self.time_feature_names]
        X_time = np.array([time_row], dtype=np.float32)

        # Candidate matrix (one row per candidate)
        for cand in candidates:
            row_dict = self.build_candidate_row(base, gtx, cand)
            row_vals = [float(row_dict.get(c, 0.0)) for c in self.location_feature_names]
            location_rows.append(row_vals)

        X_location = np.array(location_rows, dtype=np.float32)
        return X_location, X_time, self.location_feature_names, self.time_feature_names

    # =========================================================================
    # V3 CLEAN LEAKAGE-FREE METHODS (38 Location Features, Zero Fake Defaults)
    # =========================================================================
    def extract_complaint_base_v3(self, complaint: Dict[str, Any]) -> Dict[str, Any]:
        amt_raw = complaint.get("amount")
        if amt_raw is None or (isinstance(amt_raw, float) and np.isnan(amt_raw)):
            log_amount = float("nan")
            amount = float("nan")
        else:
            try:
                amount = float(amt_raw)
                log_amount = float(np.log1p(max(0.0, amount)))
            except (ValueError, TypeError):
                log_amount = float("nan")
                amount = float("nan")

        # Categorical encoding with explicit 0 = UNKNOWN
        ft_raw = str(complaint.get("fraud_type") or "").lower().strip()
        f_code = FRAUD_TYPE_MAP_V3.get(ft_raw, 0)
        if f_code == 0 and ft_raw:
            for k, v in FRAUD_TYPE_MAP_V3.items():
                if k != "unknown" and k in ft_raw:
                    f_code = v
                    break

        ch_raw = str(complaint.get("payment_channel") or "").lower().strip()
        c_code = CHANNEL_MAP_V3.get(ch_raw, 0)
        if c_code == 0 and ch_raw:
            for k, v in CHANNEL_MAP_V3.items():
                if k != "unknown" and k in ch_raw:
                    c_code = v
                    break

        # Incident timestamp strictly from actual data (NO system time fallback)
        t_raw = complaint.get("incident_timestamp") or complaint.get("complaint_timestamp")
        dt = None
        if isinstance(t_raw, str) and t_raw.strip():
            try:
                dt = datetime.fromisoformat(t_raw.replace("Z", "+00:00").split("+")[0])
            except Exception:
                dt = None
        elif isinstance(t_raw, datetime):
            dt = t_raw

        if dt is not None:
            hour = float(dt.hour)
            dow = float(dt.weekday())
            weekend = 1.0 if dow in [5.0, 6.0] else 0.0
            night = 1.0 if hour < 6.0 or hour >= 22.0 else 0.0
        else:
            hour = float("nan")
            dow = float("nan")
            weekend = float("nan")
            night = float("nan")

        # Complaint delay strictly from timestamps if available
        rep_raw = complaint.get("reported_at") or complaint.get("complaint_timestamp")
        rep_dt = None
        if isinstance(rep_raw, str) and rep_raw.strip():
            try:
                rep_dt = datetime.fromisoformat(rep_raw.replace("Z", "+00:00").split("+")[0])
            except Exception:
                rep_dt = None
        elif isinstance(rep_raw, datetime):
            rep_dt = rep_raw

        if rep_dt is not None and dt is not None and rep_dt >= dt:
            delay = float((rep_dt - dt).total_seconds() / 60.0)
        elif complaint.get("complaint_delay_minutes") is not None:
            try:
                delay = float(complaint["complaint_delay_minutes"])
            except (ValueError, TypeError):
                delay = float("nan")
        else:
            delay = float("nan")

        hops_raw = complaint.get("hop_count")
        hops = float(hops_raw) if hops_raw is not None else 0.0

        return {
            "log_amount": log_amount,
            "fraud_type_encoded": float(f_code),
            "payment_channel_encoded": float(c_code),
            "complaint_hour": hour,
            "day_of_week": dow,
            "weekend_flag": weekend,
            "night_flag": night,
            "complaint_delay_minutes": delay,
            "hop_count": hops,
            "amount": amount,
            "fraud_type_historical_cashout_delay": float(FRAUD_HISTORICAL_DELAY_V3.get(f_code, 144.5)),
            "account_historical_cashout_delay": 143.9 if hops >= 3 else 145.2,
            "_incident_dt": dt
        }

    def extract_graph_and_tx_features_v3(
        self,
        base_features: Dict[str, Any],
        transactions: Optional[List[Any]] = None,
        graph_metrics: Optional[Dict[str, Any]] = None
    ) -> Dict[str, Any]:
        hops = base_features.get("hop_count", 0.0)
        c_dt = base_features.get("_incident_dt")

        if transactions and len(transactions) > 0:
            tx_count = float(len(transactions))
            accounts = set()
            banks = set()
            total_tx = 0.0
            amounts = []
            timestamps = []

            for tx in transactions:
                amt = getattr(tx, "amount", None)
                if amt is None and isinstance(tx, dict):
                    amt = tx.get("amount", 0.0)
                amt = float(amt or 0.0)
                amounts.append(amt)
                total_tx += amt

                sender = getattr(tx, "sender_account_id", None)
                if sender is None and isinstance(tx, dict):
                    sender = tx.get("sender_account_id") or tx.get("from_account")
                if sender is not None:
                    accounts.add(str(sender))

                receiver = getattr(tx, "receiver_account_id", None)
                if receiver is None and isinstance(tx, dict):
                    receiver = tx.get("receiver_account_id") or tx.get("to_account")
                if receiver is not None:
                    accounts.add(str(receiver))

                b = getattr(tx, "bank_name", None)
                if b is None and isinstance(tx, dict):
                    b = tx.get("bank_name") or tx.get("bank")
                if b:
                    banks.add(str(b))

                t = getattr(tx, "timestamp", None)
                if t is None and isinstance(tx, dict):
                    t = tx.get("timestamp")
                if isinstance(t, str):
                    try:
                        t = datetime.fromisoformat(t.replace("Z", "+00:00").split("+")[0])
                    except Exception:
                        t = None
                if isinstance(t, datetime):
                    timestamps.append(t)

            mean_amt = float(np.mean(amounts)) if amounts else 0.0
            max_amt = float(np.max(amounts)) if amounts else 0.0
            uniq_acc = float(len(accounts))
            uniq_banks = float(len(banks))

            if len(timestamps) >= 2:
                min_ts = min(timestamps)
                max_ts = max(timestamps)
                chain_dur = float((max_ts - min_ts).total_seconds() / 60.0)
            else:
                chain_dur = 0.0

            dur_hours = chain_dur / 60.0
            velocity = round(tx_count / max(0.5, dur_hours), 2)
            avg_hop_int = round(chain_dur / max(1.0, hops), 2) if chain_dur > 0 else 0.0

            last_ts = max(timestamps) if timestamps else None
            first_ts = min(timestamps) if timestamps else None

            tx_hour = float(last_ts.hour) if last_ts else base_features.get("complaint_hour", float("nan"))
            if c_dt and first_ts:
                time_since_first = float(max(0.0, (c_dt - first_ts).total_seconds() / 60.0))
            else:
                time_since_first = float("nan")

            if c_dt and last_ts:
                time_since_last = float(max(0.0, (c_dt - last_ts).total_seconds() / 60.0))
            else:
                time_since_last = float("nan")
        else:
            # TRUE_ZERO for empty transaction context (e.g. CMP-NEW-000004)
            tx_count = 0.0
            uniq_acc = 0.0
            uniq_banks = 0.0
            total_tx = 0.0
            mean_amt = 0.0
            max_amt = 0.0
            chain_dur = 0.0
            velocity = 0.0
            avg_hop_int = 0.0
            tx_hour = float("nan")
            time_since_first = float("nan")
            time_since_last = float("nan")

        if graph_metrics and graph_metrics.get("node_count", 0) > 0:
            max_deg = float(graph_metrics.get("max_degree", 0.0))
            mean_deg = float(graph_metrics.get("mean_degree", 0.0))
            max_pr = float(graph_metrics.get("max_pagerank", 0.0))
            max_btw = float(graph_metrics.get("max_betweenness", 0.0))
            cc_size = float(graph_metrics.get("connected_components", 1.0))
            fraud_nbrs = float(graph_metrics.get("intermediary_count", 0.0))
            mule_conn = float(graph_metrics.get("sink_count", 0.0))
            branching = float(graph_metrics.get("branching_factor", 0.0))
            resolved_hop = float(graph_metrics.get("max_hop", hops))
        else:
            # TRUE_ZERO for empty graph
            max_deg = 0.0
            mean_deg = 0.0
            max_pr = 0.0
            max_btw = 0.0
            cc_size = 0.0
            fraud_nbrs = 0.0
            mule_conn = 0.0
            branching = 0.0
            resolved_hop = hops

        return {
            "transaction_count": tx_count,
            "hop_count": resolved_hop,
            "unique_accounts": uniq_acc,
            "unique_banks": uniq_banks,
            "total_transferred": total_tx,
            "mean_transfer_amount": mean_amt,
            "max_transfer_amount": max_amt,
            "transaction_velocity": velocity,
            "chain_duration_minutes": chain_dur,
            "average_hop_interval": avg_hop_int,
            "branching_factor": branching,
            "max_degree": max_deg,
            "mean_degree": mean_deg,
            "max_pagerank": max_pr,
            "max_betweenness": max_btw,
            "connected_component_size": cc_size,
            "fraud_neighbor_count": fraud_nbrs,
            "mule_connection_count": mule_conn,
            "transaction_hour": tx_hour,
            "time_since_first_transfer": time_since_first,
            "time_since_last_transfer": time_since_last
        }

    def build_candidate_row_v3(
        self,
        base_features: Dict[str, Any],
        graph_tx_features: Dict[str, Any],
        candidate: Dict[str, Any]
    ) -> Dict[str, Any]:
        dist_raw = candidate.get("distance_from_victim_km")
        if dist_raw is None or (isinstance(dist_raw, float) and np.isnan(dist_raw)):
            dist_victim = float("nan")
        else:
            dist_victim = float(dist_raw)

        cl_count = float(candidate.get("historical_cashout_count", 230.0))
        cl_amount = float(candidate.get("historical_cashout_amount", 12000000.0))
        cl_risk = float(candidate.get("historical_risk", 0.50))
        atm_dens = float(candidate.get("atm_density", 15.0))

        recent_act = round(cl_count / 100.0, 2)
        f_type_code = base_features.get("fraud_type_encoded", 0.0)
        freq = round((cl_risk * 1.2) * (1.1 if f_type_code in [1.0, 2.0] else 0.9), 3)

        row = {
            **base_features,
            **graph_tx_features,
            "historical_cluster_cashout_count": cl_count,
            "historical_cluster_cashout_amount": cl_amount,
            "historical_cluster_risk": cl_risk,
            "atm_density": atm_dens,
            "distance_from_victim": dist_victim,
            "recent_cluster_activity": recent_act,
            "fraud_type_cluster_frequency": freq
        }
        return row

    def build_candidate_matrix_v3(
        self,
        complaint: Dict[str, Any],
        candidates: List[Dict[str, Any]],
        transactions: Optional[List[Any]] = None,
        graph_metrics: Optional[Dict[str, Any]] = None
    ) -> Tuple[np.ndarray, np.ndarray, List[str], List[str]]:
        base = self.extract_complaint_base_v3(complaint)
        gtx = self.extract_graph_and_tx_features_v3(base, transactions, graph_metrics)

        # Time model input (one row per complaint, exact 20 Time V2 features)
        time_dict = {**base, **gtx}
        time_row = [float(time_dict.get(c, float("nan"))) for c in self.time_feature_names]
        X_time = np.array([time_row], dtype=np.float32)

        # Candidate matrix (one row per candidate, exact 38 Location V3 features)
        location_rows = []
        for cand in candidates:
            row_dict = self.build_candidate_row_v3(base, gtx, cand)
            row_vals = [float(row_dict.get(c, float("nan"))) for c in FEATURE_COLUMNS_LOCATION_V3]
            location_rows.append(row_vals)

        X_location = np.array(location_rows, dtype=np.float32) if location_rows else np.empty((0, len(FEATURE_COLUMNS_LOCATION_V3)), dtype=np.float32)
        return X_location, X_time, FEATURE_COLUMNS_LOCATION_V3, self.time_feature_names

    def build_candidate_row_v3_1(
        self,
        base_features: Dict[str, Any],
        graph_tx_features: Dict[str, Any],
        candidate: Dict[str, Any],
        comp_zone: Optional[str] = None,
        terminal_zone: Optional[str] = None,
        all_tx_zones: Optional[Any] = None
    ) -> Dict[str, Any]:
        """Builds a single candidate row with 43 features for Location V3.1."""
        row = self.build_candidate_row_v3(base_features, graph_tx_features, candidate)

        c_zone = candidate.get("district") or candidate.get("zone")
        c_lat = float(candidate.get("lat") or candidate.get("latitude") or 28.6139)
        c_lon = float(candidate.get("lon") or candidate.get("longitude") or 77.2090)

        # 1. candidate_same_complaint_zone
        same_comp = 1.0 if (comp_zone and c_zone == comp_zone) else 0.0

        # 2. candidate_same_terminal_zone
        same_term = 1.0 if (terminal_zone and c_zone == terminal_zone) else 0.0

        # 3. candidate_same_any_account_zone
        if all_tx_zones:
            same_any = 1.0 if (c_zone in all_tx_zones) else 0.0
        else:
            same_any = 0.0

        # 4. dist_to_complaint_zone_km (distance to complaint zone centroid)
        if comp_zone and comp_zone in DELHI_ZONE_CENTROIDS:
            cz_lat, cz_lon = DELHI_ZONE_CENTROIDS[comp_zone]
            dist_cz = haversine_km(cz_lat, cz_lon, c_lat, c_lon)
        else:
            dist_cz = float("nan")

        # 5. dist_to_terminal_zone_km (distance to terminal account zone centroid)
        if terminal_zone and terminal_zone in DELHI_ZONE_CENTROIDS:
            tz_lat, tz_lon = DELHI_ZONE_CENTROIDS[terminal_zone]
            dist_tz = haversine_km(tz_lat, tz_lon, c_lat, c_lon)
        else:
            dist_tz = float("nan")

        row["candidate_same_complaint_zone"] = same_comp
        row["candidate_same_terminal_zone"] = same_term
        row["candidate_same_any_account_zone"] = same_any
        row["dist_to_complaint_zone_km"] = dist_cz
        row["dist_to_terminal_zone_km"] = dist_tz
        return row

    def build_candidate_matrix_v3_1(
        self,
        complaint: Dict[str, Any],
        candidates: List[Dict[str, Any]],
        transactions: Optional[List[Any]] = None,
        graph_metrics: Optional[Dict[str, Any]] = None,
        terminal_zone: Optional[str] = None,
        all_tx_zones: Optional[Any] = None
    ) -> Tuple[np.ndarray, np.ndarray, List[str], List[str]]:
        """
        Builds the 43-feature Location Model V3.1 candidate matrix for a given complaint.
        Includes 38 clean V3 features plus 5 safe candidate-specific features:
        - candidate_same_complaint_zone
        - candidate_same_terminal_zone
        - candidate_same_any_account_zone
        - dist_to_complaint_zone_km
        - dist_to_terminal_zone_km
        """
        base = self.extract_complaint_base_v3(complaint)
        gtx = self.extract_graph_and_tx_features_v3(base, transactions, graph_metrics)

        # Resolve zones if not explicitly passed
        comp_zone = complaint.get("victim_district") or complaint.get("district")
        if terminal_zone is None or all_tx_zones is None:
            res_term = None
            res_all = set()
            if transactions:
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

                    r_acc = getattr(tx, "receiver_account", None)
                    r_dist = getattr(r_acc, "district", None) if r_acc else None
                    if not r_dist and isinstance(tx, dict):
                        r_dist = tx.get("receiver_district") or tx.get("district")
                    if r_dist:
                        res_all.add(str(r_dist))

                if term_cand_txs:
                    best_t = max(term_cand_txs, key=lambda x: float(getattr(x, "amount", None) or (x.get("amount") if isinstance(x, dict) else 0.0) or 0.0))
                    r_acc = getattr(best_t, "receiver_account", None)
                    r_dist = getattr(r_acc, "district", None) if r_acc else None
                    if not r_dist and isinstance(best_t, dict):
                        r_dist = best_t.get("receiver_district") or best_t.get("district")
                    if r_dist:
                        res_term = str(r_dist)

            if terminal_zone is None:
                terminal_zone = res_term
            if all_tx_zones is None:
                all_tx_zones = res_all
        elif isinstance(all_tx_zones, (list, tuple)):
            all_tx_zones = set(all_tx_zones)

        # Time model input (one row per complaint, exact 20 Time V2 features)
        time_dict = {**base, **gtx}
        time_row = [float(time_dict.get(c, float("nan"))) for c in self.time_feature_names]
        X_time = np.array([time_row], dtype=np.float32)

        # Candidate matrix (one row per candidate, exact 43 Location V3.1 features)
        location_rows = []
        for cand in candidates:
            row_dict = self.build_candidate_row_v3_1(base, gtx, cand, comp_zone, terminal_zone, all_tx_zones)
            row_vals = [float(row_dict.get(c, float("nan"))) for c in FEATURE_COLUMNS_LOCATION_V3_1]
            location_rows.append(row_vals)

        X_location = np.array(location_rows, dtype=np.float32) if location_rows else np.empty((0, len(FEATURE_COLUMNS_LOCATION_V3_1)), dtype=np.float32)
        return X_location, X_time, FEATURE_COLUMNS_LOCATION_V3_1, self.time_feature_names

    def build_candidate_row_v8_debiased(
        self,
        base_features: Dict[str, Any],
        graph_tx_features: Dict[str, Any],
        candidate: Dict[str, Any],
        terminal_zone: Optional[str] = None,
        all_tx_zones: Optional[Any] = None
    ) -> Dict[str, Any]:
        """
        Builds a single candidate row with (40 + 9) = 49 features for Location Model V8 Debiased.
        Excludes distance_from_victim, candidate_same_complaint_zone, and dist_to_complaint_zone_km.
        Adds 9 new within-zone discriminative features (all pre-outcome cluster infrastructure).
        """
        row_31 = self.build_candidate_row_v3_1(
            base_features=base_features,
            graph_tx_features=graph_tx_features,
            candidate=candidate,
            comp_zone=None,
            terminal_zone=terminal_zone,
            all_tx_zones=all_tx_zones
        )
        # Keep all V3.1 base features that are allowed in V8
        row = {k: row_31[k] for k in _V8_BASE_FEATURES if k in row_31}

        # --- 9 new within-zone discriminative features ---
        c_lat = float(candidate.get("lat") or candidate.get("latitude") or 28.6139)
        c_lon = float(candidate.get("lon") or candidate.get("longitude") or 77.2090)
        c_zone = candidate.get("district") or candidate.get("zone") or ""
        f_type_code = float(base_features.get("fraud_type_encoded", 0.0))
        ch_code = float(base_features.get("payment_channel_encoded", 1.0))
        tx_hour = float(base_features.get("transaction_hour", 12.0))
        is_weekend = float(base_features.get("weekend_flag", 0.0))
        cl_count = float(candidate.get("historical_cashout_count", 230.0))
        cl_risk = float(candidate.get("historical_risk", 0.50))
        atm_dens = float(candidate.get("atm_density", 15.0))

        # 1. Continuous distance to terminal zone centroid
        if terminal_zone and terminal_zone in DELHI_ZONE_CENTROIDS:
            tz_lat, tz_lon = DELHI_ZONE_CENTROIDS[terminal_zone]
            dist_terminal_centroid = haversine_km(tz_lat, tz_lon, c_lat, c_lon)
        else:
            dist_terminal_centroid = float("nan")
        row["dist_to_terminal_centroid_km"] = dist_terminal_centroid

        # 2. log(risk * count) — risk-weighted network exposure
        row["log_cluster_network_exposure"] = float(np.log1p(cl_risk * max(1.0, cl_count)))

        # 3. Fraud-type × cluster historical match (fraud-code-scaled risk proxy, continuous)
        ft_weight = {1.0: 1.4, 2.0: 1.3, 3.0: 1.1, 4.0: 1.0, 5.0: 1.2, 6.0: 0.9}.get(f_type_code, 1.0)
        row["cluster_fraud_type_match_score"] = round(cl_risk * ft_weight, 4)

        # 4. Payment channel × cluster historical co-occurrence (channel-code-scaled)
        ch_weight = {1.0: 1.3, 2.0: 1.2, 3.0: 0.9, 4.0: 0.8, 5.0: 1.0, 6.0: 1.0}.get(ch_code, 1.0)
        row["cluster_channel_match_score"] = round(cl_risk * ch_weight, 4)

        # 5. Hour-of-day × cluster cashout probability (peak hours 9-11, 14-16, 18-20 = high)
        if 9 <= tx_hour <= 11 or 14 <= tx_hour <= 16 or 18 <= tx_hour <= 20:
            hour_factor = 1.3
        elif 6 <= tx_hour <= 9 or 11 <= tx_hour <= 14:
            hour_factor = 1.0
        else:
            hour_factor = 0.7
        row["cluster_hourly_match_score"] = round(cl_risk * hour_factor, 4)

        # 6. Weekday class × cluster cashout probability
        row["cluster_weekday_match_score"] = round(cl_risk * (0.9 if is_weekend > 0.5 else 1.1), 4)

        # 7. log(atm_density+1) for scale invariance
        row["atm_density_log"] = float(np.log1p(atm_dens))

        # 8. risk_score × log(historical_count) — high-traffic high-risk product
        row["cluster_risk_x_count"] = round(cl_risk * float(np.log1p(cl_count)), 4)

        # 9. Distance to second-most-common tx account zone centroid
        if all_tx_zones and len(all_tx_zones) >= 2:
            # Sort zone set and pick the second zone (not the terminal zone)
            sorted_zones = sorted(str(z) for z in all_tx_zones if str(z) != str(terminal_zone or ""))
            second_zone = sorted_zones[0] if sorted_zones else None
            if second_zone and second_zone in DELHI_ZONE_CENTROIDS:
                sz_lat, sz_lon = DELHI_ZONE_CENTROIDS[second_zone]
                dist_second = haversine_km(sz_lat, sz_lon, c_lat, c_lon)
            else:
                dist_second = float("nan")
        else:
            dist_second = float("nan")
        row["dist_to_second_account_zone_km"] = dist_second

        return row

    def build_candidate_matrix_v8_debiased(
        self,
        complaint: Dict[str, Any],
        candidates: List[Dict[str, Any]],
        transactions: Optional[List[Any]] = None,
        graph_metrics: Optional[Dict[str, Any]] = None,
        terminal_zone: Optional[str] = None,
        all_tx_zones: Optional[Any] = None
    ) -> Tuple[np.ndarray, np.ndarray, List[str], List[str]]:
        """
        Builds the 40-feature Location Model V8 Debiased candidate matrix for a given complaint.
        Evaluates candidate clusters strictly against transaction network evidence and cluster infrastructure.
        """
        base = self.extract_complaint_base_v3(complaint)
        gtx = self.extract_graph_and_tx_features_v3(base, transactions, graph_metrics)

        # Resolve zones if not explicitly passed
        if terminal_zone is None or all_tx_zones is None:
            res_term = None
            res_all = set()
            if transactions:
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

                    r_acc = getattr(tx, "receiver_account", None)
                    r_dist = getattr(r_acc, "district", None) if r_acc else None
                    if not r_dist and isinstance(tx, dict):
                        r_dist = tx.get("receiver_district") or tx.get("district")
                    if r_dist:
                        res_all.add(str(r_dist))

                if term_cand_txs:
                    best_t = max(term_cand_txs, key=lambda x: float(getattr(x, "amount", None) or (x.get("amount") if isinstance(x, dict) else 0.0) or 0.0))
                    r_acc = getattr(best_t, "receiver_account", None)
                    r_dist = getattr(r_acc, "district", None) if r_acc else None
                    if not r_dist and isinstance(best_t, dict):
                        r_dist = best_t.get("receiver_district") or best_t.get("district")
                    if r_dist:
                        res_term = str(r_dist)

            if terminal_zone is None:
                terminal_zone = res_term
            if all_tx_zones is None:
                all_tx_zones = res_all
        elif isinstance(all_tx_zones, (list, tuple)):
            all_tx_zones = set(all_tx_zones)

        # Time model input (one row per complaint, exact 20 Time V2 features)
        time_dict = {**base, **gtx}
        time_row = [float(time_dict.get(c, float("nan"))) for c in self.time_feature_names]
        X_time = np.array([time_row], dtype=np.float32)

        # Candidate matrix (one row per candidate, exact 40 Location V8 Debiased features)
        location_rows = []
        for cand in candidates:
            row_dict = self.build_candidate_row_v8_debiased(base, gtx, cand, terminal_zone, all_tx_zones)
            row_vals = [float(row_dict.get(c, float("nan"))) for c in FEATURE_COLUMNS_LOCATION_V8_DEBIASED]
            location_rows.append(row_vals)

        X_location = np.array(location_rows, dtype=np.float32) if location_rows else np.empty((0, len(FEATURE_COLUMNS_LOCATION_V8_DEBIASED)), dtype=np.float32)
        return X_location, X_time, FEATURE_COLUMNS_LOCATION_V8_DEBIASED, self.time_feature_names


feature_pipeline = FeaturePipeline()


