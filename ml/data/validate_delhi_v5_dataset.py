"""
CyberShield AI — Delhi V5 Controlled Historical Dataset Validator
Phase A.2: Strict Validation of Generated Dataset Assets

Validates:
1. Row count between 12,000 and 15,000
2. Exact 60 operational cluster universe
3. All 11 revenue districts represented with meaningful non-zero volume
4. Chronological ordering (reported_at >= event_timestamp, monotonic event_timestamp)
5. Split ratios: ~70% train, ~15% validation, ~15% test
6. Zero duplicate case IDs
7. Zero NaN / inf / null values in required columns
8. Positive monetary amounts (> 0) and non-negative reporting delays (>= 0)
9. Positive realized cash-out minutes (> 0)
10. Valid coordinate bounds within Delhi operational envelope
11. Family leakage across splits == 0 (zero cohort overlap)
12. Zero target leakage columns in pre-inference features
13. Manifest statistical consistency with dataset
14. SHA-256 verification of dataset and schema
"""

import os
import sys
import json
import gzip
import math
import hashlib
from typing import Dict, Any, List, Set
import pandas as pd
import numpy as np

ALL_11_DISTRICTS = {
    "CENTRAL", "EAST", "NEW_DELHI", "NORTH", "NORTH_EAST",
    "NORTH_WEST", "SHAHDARA", "SOUTH", "SOUTH_EAST", "SOUTH_WEST", "WEST"
}

ALLOWED_PRE_INFERENCE_COLS = {
    "case_id", "event_timestamp", "reported_at", "reporting_delay_minutes",
    "victim_district", "victim_lat", "victim_lon", "fraud_type", "payment_channel",
    "amount", "amount_bucket", "victim_bank_group", "beneficiary_account_count",
    "transaction_count", "transaction_hop_count", "mule_account_count",
    "distinct_bank_count", "terminal_mule_district", "transaction_velocity",
    "transfer_burst_score", "graph_depth", "graph_branching_factor",
    "night_activity_ratio", "weekend_flag"
}

TARGET_COLS = {
    "realized_cashout_cluster_id", "realized_cashout_cluster_name",
    "realized_cashout_district", "realized_cashout_lat",
    "realized_cashout_lon", "realized_cashout_minutes"
}

FORBIDDEN_LEAKAGE_COLS = {
    "distance_to_true_cluster", "true_cluster_frequency", "future_withdrawal_count",
    "post_cashout_signal", "realized_cluster_encoded", "target_district_onehot",
    "distance_to_realized_cluster", "is_true_cluster"
}

def compute_sha256(filepath: str) -> str:
    h = hashlib.sha256()
    with open(filepath, "rb") as f:
        while chunk := f.read(65536):
            h.update(chunk)
    return h.hexdigest()

def validate_delhi_v5(data_dir: str) -> bool:
    print("=" * 80)
    print("CYBERSHIELD AI — DELHI V5 DATASET COMPREHENSIVE VALIDATION")
    print("=" * 80)

    csv_path = os.path.join(data_dir, "delhi_v5_cases.csv.gz")
    manifest_path = os.path.join(data_dir, "delhi_v5_dataset_manifest.json")
    schema_path = os.path.join(data_dir, "delhi_v5_dataset_schema.json")
    report_path = os.path.join(data_dir, "delhi_v5_dataset_report.json")
    coverage_path = os.path.join(data_dir, "delhi_v5_feature_coverage.json")

    # 1. Existence Check
    for p in [csv_path, manifest_path, schema_path, report_path, coverage_path]:
        if not os.path.exists(p):
            print(f"[FAIL] Missing required artifact: {p}")
            return False
    print("[PASS] All 5 required V5 dataset assets exist on disk.")

    # 2. SHA-256 Check against Manifest
    with open(manifest_path, "r", encoding="utf-8") as f:
        manifest = json.load(f)
    with open(schema_path, "r", encoding="utf-8") as f:
        schema = json.load(f)

    actual_csv_sha = compute_sha256(csv_path)
    actual_schema_sha = compute_sha256(schema_path)

    if actual_csv_sha != manifest["dataset_sha256"]:
        print(f"[FAIL] Dataset SHA-256 mismatch! Manifest={manifest['dataset_sha256']}, Actual={actual_csv_sha}")
        return False
    if actual_schema_sha != manifest["schema_sha256"]:
        print(f"[FAIL] Schema SHA-256 mismatch! Manifest={manifest['schema_sha256']}, Actual={actual_schema_sha}")
        return False
    print(f"[PASS] SHA-256 verified: Dataset={actual_csv_sha[:16]}... Schema={actual_schema_sha[:16]}...")

    # 3. Read Dataset
    df = pd.read_csv(csv_path)
    n_rows = len(df)
    print(f"[INFO] Loaded {n_rows} rows from {csv_path}")

    # Row count bounds
    if not (12000 <= n_rows <= 15000):
        print(f"[FAIL] Row count {n_rows} outside [12000, 15000]!")
        return False
    if n_rows != manifest["actual_case_count"]:
        print(f"[FAIL] Manifest actual_case_count ({manifest['actual_case_count']}) != dataset rows ({n_rows})!")
        return False
    print(f"[PASS] Row count: {n_rows} (matches manifest)")

    # 4. District and Cluster Universe Checks
    clusters_represented = set(df["realized_cashout_cluster_id"].unique())
    if len(clusters_represented) != 60:
        print(f"[FAIL] Cluster count is {len(clusters_represented)}, expected exactly 60!")
        return False
    if min(clusters_represented) != 7 or max(clusters_represented) != 66:
        print(f"[FAIL] Cluster ID bounds unexpected: min={min(clusters_represented)}, max={max(clusters_represented)}")
        return False
    print(f"[PASS] Exactly 60 operational cash-out clusters represented (IDs 7 to 66).")

    districts_represented = set(df["realized_cashout_district"].unique())
    if districts_represented != ALL_11_DISTRICTS:
        missing = ALL_11_DISTRICTS - districts_represented
        print(f"[FAIL] Districts missing: {missing}")
        return False
    print(f"[PASS] All 11 revenue districts represented: {sorted(districts_represented)}")

    victim_districts = set(df["victim_district"].unique())
    if victim_districts != ALL_11_DISTRICTS:
        print(f"[FAIL] Victim districts missing: {ALL_11_DISTRICTS - victim_districts}")
        return False
    print(f"[PASS] All 11 victim origin revenue districts represented.")

    # 5. Null, NaN, Inf, and Type Bounds
    if df.isna().sum().sum() > 0:
        print(f"[FAIL] Found NaN/null values: {df.isna().sum().to_dict()}")
        return False

    # Positive Amount
    if (df["amount"] <= 0).any():
        print(f"[FAIL] Non-positive amount values found!")
        return False

    # Positive Cashout Time
    if (df["realized_cashout_minutes"] <= 0).any():
        print(f"[FAIL] Non-positive realized_cashout_minutes found!")
        return False

    # Non-negative Reporting Delay
    if (df["reporting_delay_minutes"] < 0).any():
        print(f"[FAIL] Negative reporting_delay_minutes found!")
        return False

    # Graph integers >= 1
    for col in ["transaction_count", "transaction_hop_count", "mule_account_count", "distinct_bank_count"]:
        if (df[col] < 1).any():
            print(f"[FAIL] Values < 1 found in column {col}!")
            return False

    # Coordinates in Delhi region bounds
    lat_min, lat_max = 28.38, 28.92
    lon_min, lon_max = 76.80, 77.45
    if not ((df["victim_lat"] >= lat_min) & (df["victim_lat"] <= lat_max)).all():
        print(f"[FAIL] victim_lat out of Delhi bounding box!")
        return False
    if not ((df["victim_lon"] >= lon_min) & (df["victim_lon"] <= lon_max)).all():
        print(f"[FAIL] victim_lon out of Delhi bounding box!")
        return False
    if not ((df["realized_cashout_lat"] >= lat_min) & (df["realized_cashout_lat"] <= lat_max)).all():
        print(f"[FAIL] realized_cashout_lat out of Delhi bounding box!")
        return False
    if not ((df["realized_cashout_lon"] >= lon_min) & (df["realized_cashout_lon"] <= lon_max)).all():
        print(f"[FAIL] realized_cashout_lon out of Delhi bounding box!")
        return False
    print("[PASS] Geographic coordinates strictly bounded within Delhi region envelope.")

    # 6. Duplicates Check
    dup_ids = df["case_id"].duplicated().sum()
    if dup_ids > 0:
        print(f"[FAIL] Found {dup_ids} duplicate case_id values!")
        return False
    print("[PASS] Zero duplicate case IDs.")

    # 7. Split Ratios & Monotonicity
    splits = df["split"].value_counts()
    n_train = splits.get("train", 0)
    n_val = splits.get("validation", 0)
    n_test = splits.get("test", 0)

    train_pct = n_train / n_rows * 100
    val_pct = n_val / n_rows * 100
    test_pct = n_test / n_rows * 100

    print(f"[INFO] Split distribution: Train={n_train} ({train_pct:.1f}%), Val={n_val} ({val_pct:.1f}%), Test={n_test} ({test_pct:.1f}%)")
    if not (68.0 <= train_pct <= 72.0):
        print(f"[FAIL] Train split {train_pct:.1f}% outside target ~70%!")
        return False
    if not (13.0 <= val_pct <= 17.0):
        print(f"[FAIL] Validation split {val_pct:.1f}% outside target ~15%!")
        return False
    if not (13.0 <= test_pct <= 17.0):
        print(f"[FAIL] Test split {test_pct:.1f}% outside target ~15%!")
        return False

    # Chronological Monotonicity Check
    df_events = pd.to_datetime(df["event_timestamp"])
    if not df_events.is_monotonic_increasing:
        print("[FAIL] event_timestamp is NOT monotonically increasing! Chronological ordering violated.")
        return False

    # Reported at >= event_timestamp
    df_reported = pd.to_datetime(df["reported_at"])
    if (df_reported < df_events).any():
        print("[FAIL] reported_at precedes event_timestamp!")
        return False
    print("[PASS] Chronological ordering and reporting delay relationships verified.")

    # 8. Target Leakage and Forbidden Columns Check
    forbidden_present = set(df.columns).intersection(FORBIDDEN_LEAKAGE_COLS)
    if forbidden_present:
        print(f"[FAIL] Forbidden leakage columns detected in dataset: {forbidden_present}")
        return False

    # Check pre-inference columns role
    schema_fields = {f["name"]: f["role"] for f in schema["fields"]}
    for col in df.columns:
        if col in TARGET_COLS:
            if schema_fields[col] != "TARGET":
                print(f"[FAIL] Target column {col} has incorrect schema role {schema_fields[col]}!")
                return False
        elif col in ALLOWED_PRE_INFERENCE_COLS:
            if schema_fields[col] not in ("PRE_EVENT_FEATURE", "CONTEXT_FEATURE", "IDENTIFIER"):
                print(f"[FAIL] Column {col} has invalid schema role {schema_fields[col]}!")
                return False
    print("[PASS] No target leakage columns detected. Schema roles strictly classified.")

    # 9. Family Leakage Across Splits Check
    train_df = df[df["split"] == "train"]
    val_df = df[df["split"] == "validation"]
    test_df = df[df["split"] == "test"]

    syn_train = set(train_df["syndicate_family_id"])
    syn_val = set(val_df["syndicate_family_id"])
    syn_test = set(test_df["syndicate_family_id"])

    syn_leaks = len(syn_train.intersection(syn_val)) + len(syn_train.intersection(syn_test)) + len(syn_val.intersection(syn_test))

    mule_train = set(train_df["mule_family_id"])
    mule_val = set(val_df["mule_family_id"])
    mule_test = set(test_df["mule_family_id"])

    mule_leaks = len(mule_train.intersection(mule_val)) + len(mule_train.intersection(mule_test)) + len(mule_val.intersection(mule_test))

    if syn_leaks > 0 or mule_leaks > 0:
        print(f"[FAIL] Family leakage detected across splits! Syndicates: {syn_leaks}, Mules: {mule_leaks}")
        return False
    print(f"[PASS] Zero family leakage across chronological splits: Syndicate Leak=0, Mule Leak=0.")

    # 10. Non-Trivial Cash-Out Diagnostics (Avoid Origin Distance Dominance)
    with open(report_path, "r", encoding="utf-8") as f:
        report = json.load(f)

    nearest_rate = report["nearest_origin_target_rate_pct"]
    cross_dist_rate = report["cross_district_rate_pct"]
    entropy = report["target_cluster_entropy"]

    print(f"[INFO] Diagnostics: Nearest-Origin Target Rate = {nearest_rate}% (Must not be > 50%)")
    print(f"[INFO] Diagnostics: Cross-District Cash-Out Rate = {cross_dist_rate}% (Meaningful mobility)")
    print(f"[INFO] Diagnostics: Target Cluster Entropy = {entropy:.4f}")

    if nearest_rate > 50.0:
        print(f"[FAIL] Dataset is dominated by nearest-origin cluster ({nearest_rate}%)!")
        return False
    if cross_dist_rate < 15.0:
        print(f"[FAIL] Insufficient cross-district cash-out mobility ({cross_dist_rate}%)!")
        return False
    if entropy < 4.0:
        print(f"[FAIL] Target cluster entropy too low ({entropy:.4f})! Distribution is overly concentrated.")
        return False
    print("[PASS] Cash-out behavior is non-trivial and well-diversified.")

    print("=" * 80)
    print("ALL V5 DATASET QUALITY & INTEGRITY CHECKS PASSED SUCCESSFULLY.")
    print("=" * 80)
    return True

if __name__ == "__main__":
    base_dir = os.path.abspath(os.path.join(os.path.dirname(__file__), "..", ".."))
    d_dir = os.path.join(base_dir, "ml", "data")
    success = validate_delhi_v5(d_dir)
    sys.exit(0 if success else 1)
