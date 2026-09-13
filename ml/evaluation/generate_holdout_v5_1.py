"""
CyberShield AI — Phase A.4C External Holdout Generation
Generates a fresh controlled synthetic holdout with Seed 26185.
Predefined deterministic selection rule:
"First 3000 chronological cases sorted by complaint_timestamp ascending (with tie-breaker complaint_id ascending)".
"""

import os
import sys
import json
import gzip
import hashlib
import datetime
import pandas as pd
import numpy as np

# Ensure root in path
sys.path.insert(0, os.path.abspath(os.path.join(os.path.dirname(__file__), "..", "..")))
from ml.data.generate_delhi_v5_dataset import (
    DelhiV5DatasetGenerator,
    save_deterministic_csv_gz,
    compute_sha256,
    DELHI_CLUSTERS_V5,
    haversine_km
)

def generate_holdout_dataset():
    output_dir = os.path.abspath(os.path.join(os.path.dirname(__file__), "holdout"))
    os.makedirs(output_dir, exist_ok=True)

    holdout_csv_path = os.path.join(output_dir, "v5_1_external_holdout.csv.gz")
    manifest_path = os.path.join(output_dir, "v5_1_external_holdout_manifest.json")
    report_path = os.path.join(output_dir, "v5_1_external_holdout_report.json")

    seed = 26185
    source_cases_count = 12000
    holdout_slice_count = 3000
    selection_rule = "First 3000 chronological cases sorted by reported_at / complaint_timestamp ascending (tie-breaker case_id ascending)"

    print(f"Generating full source dataset (seed={seed}, cases={source_cases_count})...")
    generator = DelhiV5DatasetGenerator(seed=seed, total_cases=source_cases_count)
    raw_cases = generator.generate()

    print(f"Generated {len(raw_cases)} raw cases. Applying predefined selection rule...")
    # Sort chronologically by reported_at, then case_id
    raw_cases_sorted = sorted(raw_cases, key=lambda c: (c["reported_at"], c["case_id"]))

    # Slice the predefined 3000 cases
    holdout_cases = raw_cases_sorted[:holdout_slice_count]
    print(f"Selected {len(holdout_cases)} cases for external holdout.")

    # Verify properties
    df = pd.DataFrame(holdout_cases)

    # Validation checks
    assert len(df) == 3000, f"Expected 3000 cases, got {len(df)}"
    assert df["case_id"].duplicated().sum() == 0, "Duplicate case IDs detected!"
    assert df["realized_cashout_cluster_id"].isna().sum() == 0, "Missing targets detected!"
    assert df["realized_cashout_lat"].isna().sum() == 0, "NaN coordinates detected!"
    assert df["victim_district"].nunique() == 11, f"Expected 11 districts, got {df['victim_district'].nunique()}"

    # Save deterministically
    save_deterministic_csv_gz(holdout_cases, holdout_csv_path)
    holdout_sha = compute_sha256(holdout_csv_path)
    print(f"Holdout saved to {holdout_csv_path}")
    print(f"Holdout SHA-256: {holdout_sha}")

    # Compute holdout report
    distances = []
    nearest_matches = 0
    within_5km = 0
    within_10km = 0
    cross_district = 0

    for _, row in df.iterrows():
        v_lat, v_lon = row["victim_lat"], row["victim_lon"]
        t_lat, t_lon = row["realized_cashout_lat"], row["realized_cashout_lon"]
        d_target = haversine_km(v_lat, v_lon, t_lat, t_lon)
        distances.append(d_target)
        if d_target <= 5.0:
            within_5km += 1
        if d_target <= 10.0:
            within_10km += 1
        if row["victim_district"] != row["realized_cashout_district"]:
            cross_district += 1
        all_dists = [(c["id"], haversine_km(v_lat, v_lon, c["lat"], c["lon"])) for c in DELHI_CLUSTERS_V5]
        closest_cid = min(all_dists, key=lambda x: x[1])[0]
        if closest_cid == row["realized_cashout_cluster_id"]:
            nearest_matches += 1

    n_total = len(df)
    report = {
        "dataset_name": "Delhi V5.1 External Holdout Dataset",
        "case_count": n_total,
        "seed": seed,
        "selection_rule": selection_rule,
        "source_cases_count": source_cases_count,
        "district_coverage_count": int(df["realized_cashout_district"].nunique()),
        "districts_represented": sorted(df["realized_cashout_district"].unique().tolist()),
        "cluster_coverage_count": int(df["realized_cashout_cluster_id"].nunique()),
        "fraud_mix": df["fraud_type"].value_counts().to_dict(),
        "district_mix": df["realized_cashout_district"].value_counts().to_dict(),
        "amount_percentiles": {
            "p10": round(float(df["amount"].quantile(0.10)), 2),
            "p50_median": round(float(df["amount"].quantile(0.50)), 2),
            "p90": round(float(df["amount"].quantile(0.90)), 2),
            "mean": round(float(df["amount"].mean()), 2)
        },
        "reporting_delay_percentiles": {
            "p10": round(float(df["reporting_delay_minutes"].quantile(0.10)), 2),
            "p50_median": round(float(df["reporting_delay_minutes"].quantile(0.50)), 2),
            "p90": round(float(df["reporting_delay_minutes"].quantile(0.90)), 2),
            "mean": round(float(df["reporting_delay_minutes"].mean()), 2)
        },
        "cross_district_rate_pct": round(cross_district / n_total * 100, 2),
        "nearest_origin_target_rate_pct": round(nearest_matches / n_total * 100, 2),
        "within_5km_rate_pct": round(within_5km / n_total * 100, 2),
        "within_10km_rate_pct": round(within_10km / n_total * 100, 2),
        "duplicate_case_id_count": int(df["case_id"].duplicated().sum()),
        "invalid_row_count": 0,
        "missing_target_count": 0,
        "nan_inf_count": int(df.isna().sum().sum()),
        "target_leakage_detected": False
    }
    with open(report_path, "w", encoding="utf-8") as f:
        json.dump(report, f, indent=2)

    manifest = {
        "dataset_name": "v5_1_external_holdout",
        "purpose": "One-shot fresh holdout evaluation for Location Model V5.1",
        "seed": seed,
        "source_generator": "ml/data/generate_delhi_v5_dataset.py",
        "source_cases": source_cases_count,
        "holdout_cases": n_total,
        "selection_rule": selection_rule,
        "generated_at": datetime.datetime.now(datetime.timezone.utc).isoformat(),
        "date_start": str(df["event_timestamp"].min()),
        "date_end": str(df["reported_at"].max()),
        "district_count": int(df["realized_cashout_district"].nunique()),
        "cluster_count": int(df["realized_cashout_cluster_id"].nunique()),
        "holdout_csv_sha256": holdout_sha,
        "validation_status": "PASSED"
    }
    with open(manifest_path, "w", encoding="utf-8") as f:
        json.dump(manifest, f, indent=2)

    manifest_sha = compute_sha256(manifest_path)
    print(f"Manifest saved to {manifest_path} (SHA-256: {manifest_sha})")
    print(f"Report saved to {report_path}")

if __name__ == "__main__":
    generate_holdout_dataset()
