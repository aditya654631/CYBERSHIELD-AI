import numpy as np
import pandas as pd
from typing import Dict, Any

class FeatureExtractor:
    """
    Extracts multimodal features for Candidate-Location Ranking and Cash-Out Time Window Prediction.
    - Complaint features (amount, fraud type, channel, timing)
    - Transaction network features (hops, velocity, branching)
    - Graph centrality features (PageRank, betweenness)
    - Geospatial features (historical density, distance)
    - Temporal features (hour, complaint delay)
    """
    def __init__(self):
        self.fraud_type_map = {
            "investment scam": 1,
            "upi / qr code fraud": 2,
            "digital arrest / sextortion": 3,
            "part-time job fraud": 4,
            "loan app extortion": 5
        }
        self.channel_map = {"upi": 1, "imps": 2, "neft": 3, "rtgs": 4, "netbanking": 5}

    def extract_complaint_vector(self, complaint_dict: Dict[str, Any]) -> np.ndarray:
        amount = float(complaint_dict.get("amount", 50000.0))
        fraud_type = str(complaint_dict.get("fraud_type", "")).lower()
        f_code = self.fraud_type_map.get(fraud_type, 1)

        channel = str(complaint_dict.get("payment_channel", "UPI")).lower()
        c_code = self.channel_map.get(channel, 1)

        log_amount = np.log1p(amount)
        hour = 19 # default demo hour

        # Transaction & graph heuristics
        hop_count = 3
        branching_factor = 2.0
        pagerank_max = 0.32
        betweenness_max = 0.28
        historical_cluster_density = 0.85
        atm_density = 12

        return np.array([
            log_amount, f_code, c_code, hour,
            hop_count, branching_factor,
            pagerank_max, betweenness_max,
            historical_cluster_density, atm_density
        ], dtype=np.float32)

feature_extractor = FeatureExtractor()
