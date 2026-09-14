"""
Audit Suite: Synthetic Blockchain Signal Causality & Anti-Leakage
Verifies:
1. Strict Temporal Causality (event_timestamp <= T_ref, submitted_at <= T_ref)
2. No Direct Target Encoding (signals distributed across candidates, target not uniquely flagged)
3. Non-Trivial Shortcut Absence (feature correlations with target label strictly below leakage threshold)
"""

import numpy as np
import pytest
from datetime import datetime, timezone
from ml.training.blockchain_signal_generator import CausalBlockchainSignalGenerator
from ml.features.blockchain_feature_extractor import extract_candidate_blockchain_features, ORDERED_BLOCKCHAIN_FEATURES

def test_signal_temporal_causality():
    generator = CausalBlockchainSignalGenerator(seed=12345)
    candidates = [
        {"id": i, "zone": f"Zone_{i%5}", "risk": 0.4 + (i%5)*0.1, "historical_cashout_count": 150}
        for i in range(1, 26)
    ]
    all_clusters = candidates

    t_ref_iso = "2026-09-14T14:30:00.000Z"
    complaint = {
        "complaint_number": "CMP-AUDIT-001",
        "amount": 45000.0,
        "reported_at": t_ref_iso,
        "payment_channel": "upi",
        "victim_district": "Zone_2"
    }

    t_ref_dt = datetime.fromisoformat("2026-09-14T14:30:00+00:00")

    for case_idx in range(50):
        complaint["complaint_number"] = f"CMP-AUDIT-{case_idx:04d}"
        cluster_sigs, subj_sigs = generator.generate_pre_outcome_signals(
            complaint=complaint,
            candidate_clusters=candidates,
            all_delhi_clusters=all_clusters,
            terminal_zone="Zone_2"
        )

        for sig in cluster_sigs:
            e_dt = datetime.fromisoformat(sig["event_timestamp"])
            s_dt = datetime.fromisoformat(sig["submitted_at"])
            assert e_dt <= t_ref_dt, f"Leakage detected! Event time {e_dt} > Ref time {t_ref_dt}"
            assert s_dt <= t_ref_dt, f"Leakage detected! Submission time {s_dt} > Ref time {t_ref_dt}"

        for sig in subj_sigs:
            e_dt = datetime.fromisoformat(sig["event_timestamp"])
            s_dt = datetime.fromisoformat(sig["submitted_at"])
            assert e_dt <= t_ref_dt
            assert s_dt <= t_ref_dt


def test_no_direct_target_encoding():
    generator = CausalBlockchainSignalGenerator(seed=6789)
    candidates = [
        {"id": i, "zone": f"Zone_{i%5}", "risk": 0.5, "historical_cashout_count": 200}
        for i in range(1, 26)
    ]
    all_clusters = candidates

    target_clusters_with_zero_signals = 0
    non_targets_with_signals = 0
    total_cases = 100

    for case_idx in range(total_cases):
        target_cluster_id = (case_idx % 25) + 1
        complaint = {
            "complaint_number": f"CMP-AUDIT-NOLEAK-{case_idx}",
            "amount": 30000.0 + case_idx * 500,
            "reported_at": "2026-09-14T12:00:00.000Z",
            "payment_channel": "upi",
            "victim_district": "Zone_1"
        }

        cluster_sigs, _ = generator.generate_pre_outcome_signals(
            complaint=complaint,
            candidate_clusters=candidates,
            all_delhi_clusters=all_clusters,
            terminal_zone="Zone_1"
        )

        sig_clusters = set(s["cluster_id"] for s in cluster_sigs)

        if target_cluster_id not in sig_clusters:
            target_clusters_with_zero_signals += 1

        non_target_sigs = [cid for cid in sig_clusters if cid != target_cluster_id]
        if len(non_target_sigs) > 0:
            non_targets_with_signals += 1

    # In realistic consortium intelligence, signals are not a 1-to-1 mirror of ground truth
    assert target_clusters_with_zero_signals > 0, "Target cluster ALWAYS has signals (deterministic shortcut detected!)"
    assert non_targets_with_signals > 50, "Non-target clusters rarely have signals (overly targeted emission!)"


def test_shortcut_correlation_audit():
    """
    Computes Pearson correlation between all blockchain features and target indicator y.
    Asserts max correlation < 0.60, demonstrating no trivial shortcut or direct target leakage.
    """
    generator = CausalBlockchainSignalGenerator(seed=999)
    candidates = [
        {"id": i, "zone": f"Zone_{i%4}", "risk": 0.3 + (i%4)*0.15, "historical_cashout_count": 100 + i*10}
        for i in range(1, 26)
    ]
    all_clusters = candidates

    y_list = []
    feat_matrix = {feat: [] for feat in ORDERED_BLOCKCHAIN_FEATURES}

    for case_idx in range(100):
        target_cid = (case_idx % 25) + 1
        t_ref = "2026-09-14T12:00:00.000Z"
        complaint = {
            "complaint_number": f"CMP-CORR-{case_idx}",
            "amount": 20000.0 + case_idx * 100,
            "reported_at": t_ref,
            "payment_channel": "upi",
            "victim_district": f"Zone_{case_idx%4}"
        }

        cluster_sigs, subj_sigs = generator.generate_pre_outcome_signals(
            complaint=complaint,
            candidate_clusters=candidates,
            all_delhi_clusters=all_clusters,
            terminal_zone=f"Zone_{case_idx%4}"
        )

        for cand in candidates:
            cid = cand["id"]
            y = 1 if cid == target_cid else 0
            y_list.append(y)

            extracted = extract_candidate_blockchain_features(
                cluster_id=cid,
                reference_timestamp=t_ref,
                raw_signals=cluster_sigs,
                opaque_subject_ref=None,
                raw_subject_signals=None,
                fabric_available=True
            )
            for feat in ORDERED_BLOCKCHAIN_FEATURES:
                feat_matrix[feat].append(float(extracted["features"].get(feat, 0)))

    y_arr = np.array(y_list)
    correlations = {}
    for feat in ORDERED_BLOCKCHAIN_FEATURES:
        x_arr = np.array(feat_matrix[feat])
        std_x = np.std(x_arr)
        std_y = np.std(y_arr)
        if std_x > 1e-6 and std_y > 1e-6:
            r = float(np.corrcoef(x_arr, y_arr)[0, 1])
        else:
            r = 0.0
        correlations[feat] = r

    max_corr_feat = max(correlations.items(), key=lambda x: abs(x[1]))
    print(f"Max correlation with target label: {max_corr_feat[0]} = {max_corr_feat[1]:.4f}")

    # Leakage assertion: no feature can have abs(correlation) >= 0.60
    assert abs(max_corr_feat[1]) < 0.60, f"Shortcut Leakage Detected! Feature {max_corr_feat[0]} has correlation {max_corr_feat[1]:.4f} >= 0.60"
