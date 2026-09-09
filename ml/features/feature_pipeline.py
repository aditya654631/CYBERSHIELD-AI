"""
Feature Pipeline for CyberShield AI Location Ranking & Time-to-Cashout Models
Extracts multimodal features across:
1. Complaint characteristics
2. Transaction topology & velocity
3. Graph centrality & mule proximity
4. Candidate cluster geospatial metrics
5. Temporal dynamics & delay signals
"""

import numpy as np
import pandas as pd
from datetime import datetime
from typing import Dict, Any, List, Optional, Tuple

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

feature_pipeline = FeaturePipeline()
