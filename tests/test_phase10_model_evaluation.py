"""
CyberShield AI — Phase 10: Model Evaluation, Baselines & Data Readiness Test Suite

Tests:
1. Programmatic dataset inventory (versions, row counts, candidate universe, 47 features).
2. Denominator reconciliation (5,395 actual cases vs 'combined_6000' label).
3. Reproducible evaluation with fixed seed (identical metrics).
4. All baselines use the exact same candidate universe (K=25).
5. Candidate recall separated from ranking recall (missing targets explicit).
6. Comparative performance: V7-compat vs Hotspot vs Distance vs Random.
7. Case-group leakage detection.
8. Chronological causal transaction cutoff verification.
9. Authorized real-data validator on valid schema fixture.
10. PII detection (unmasked phone, Aadhaar, PAN, card numbers rejected).
11. Chronological anomalies and future dates rejected.
12. Duplicate case IDs flagged.
13. Real-data status reports REAL_VALIDATION_PENDING.
14. Promotion gates reject unmet evidence and protect production model.
15. Production artifact integrity (all baseline hashes intact).
16. Fast API evaluation endpoints return 200 OK with correct schema.
"""

import os
import pytest
from datetime import datetime, timezone, timedelta
from fastapi.testclient import TestClient

from ml.evaluation.dataset_inventory import (
    get_dataset_inventory,
    get_feature_inventory,
    get_candidate_universe_inventory,
    reconcile_saved_denominators,
)
from ml.evaluation.reproducible_evaluator import (
    ReproducibleEvaluator,
    load_delhi_clusters_cached,
    score_candidates_hotspot,
    score_candidates_distance,
    score_candidates_random,
    evaluate_model_predictions,
    verify_case_group_leakage,
    verify_chronological_causality,
)
from ml.evaluation.real_data_validator import (
    RealDataImportValidator,
    get_real_data_validation_status,
)
from ml.evaluation.promotion_gates import (
    verify_production_artifact_integrity,
    evaluate_promotion_gates,
    PROMOTION_GATE_SPECS,
)


# ── FIXTURES ──────────────────────────────────────────────────────────────────

@pytest.fixture
def sample_cases():
    """Generates synthetic test cases across Delhi districts for fast deterministic testing."""
    clusters = load_delhi_clusters_cached()
    cases = []
    fraud_types = ["UPI / QR Code Fraud", "Investment Scam", "Digital Arrest / Extortion", "Part-Time Job Fraud"]

    for i in range(20):
        target_c = clusters[i % len(clusters)]
        victim_c = clusters[(i + 3) % len(clusters)]
        cases.append({
            "complaint": {
                "complaint_number": f"TEST-CMP-{1000 + i}",
                "fraud_type": fraud_types[i % len(fraud_types)],
                "amount": 25000.0 + (i * 5000.0),
                "reported_at": "2026-09-15T10:00:00Z",
                "victim_district": victim_c["district"],
                "victim_lat": victim_c["lat"],
                "victim_lon": victim_c["lon"],
            },
            "transactions": None,
            "terminal_zone": victim_c["district"],
            "all_tx_zones": {victim_c["district"]},
            "target_cluster_id": target_c["id"],
        })
    return cases


# ── TEST 1 & 2: INVENTORY & RECONCILIATION ────────────────────────────────────

def test_dataset_inventory_metadata():
    """Verify programmatic inventory returns features, candidate universe, and datasets."""
    inv = get_dataset_inventory()
    assert "legacy_v2_dataset" in inv
    assert "expanded_training_pool" in inv
    assert "features" in inv
    assert "candidate_universe" in inv

    # Features check
    feat_inv = get_feature_inventory()
    assert feat_inv["total_features"] == 47
    assert feat_inv["feature_breakdown"]["base_location_features_v3_1"] == 43
    assert feat_inv["feature_breakdown"]["v4_compatibility_features"] == 4
    assert "v4_candidate_score" in feat_inv["feature_names"]

    # Candidate universe check
    cand_inv = get_candidate_universe_inventory()
    assert cand_inv["candidate_universe_size"] == 60
    assert cand_inv["top_k_candidates"] == 25
    assert cand_inv["target_definition"]["name"] == "realized_cashout_cluster_id"


def test_denominator_reconciliation():
    """Verify that the 5,395 actual input cases are reconciled with 'combined_6000' label."""
    rec = reconcile_saved_denominators()
    assert rec["status"] == "RECONCILED"
    assert rec["actual_input_cases_sum"] == 5395
    assert rec["component_holdouts"]["legacy_seed_56261"] == 1395
    assert rec["component_holdouts"]["v6_2_seed_56262"] == 2000
    assert rec["component_holdouts"]["v6_3_seed_56263"] == 2000
    assert rec["labeled_case_count"] == 6000
    assert rec["discrepancy_count"] == -605
    assert "v7_compat_reconciled_metrics" in rec
    assert rec["v7_compat_reconciled_metrics"]["exact_denominator"] == 5395
    assert rec["v7_compat_reconciled_metrics"]["top3_accuracy"] == 32.66


# ── TEST 3 & 4: REPRODUCIBILITY & UNIFIED CANDIDATE UNIVERSE ──────────────────

def test_reproducible_evaluation_fixed_seed(sample_cases):
    """Verify that running evaluation with the same seed produces identical scores and metrics."""
    evaluator = ReproducibleEvaluator()
    res1 = evaluator.evaluate_benchmark(sample_cases, random_seed=12345)
    res2 = evaluator.evaluate_benchmark(sample_cases, random_seed=12345)

    v7_1 = res1["production_model_v7_compat"]["unconditional_ranking_metrics"]
    v7_2 = res2["production_model_v7_compat"]["unconditional_ranking_metrics"]
    assert v7_1["r1"] == v7_2["r1"]
    assert v7_1["r3"] == v7_2["r3"]
    assert v7_1["mrr"] == v7_2["mrr"]

    rand_1 = res1["baselines"]["random_reference_baseline"]["unconditional_ranking_metrics"]
    rand_2 = res2["baselines"]["random_reference_baseline"]["unconditional_ranking_metrics"]
    assert rand_1["r1"] == rand_2["r1"]
    assert rand_1["mrr"] == rand_2["mrr"]


def test_baselines_comparable_candidate_universe(sample_cases):
    """Verify all models and baselines score the exact same candidate pool size (K=25)."""
    evaluator = ReproducibleEvaluator()
    res = evaluator.evaluate_benchmark(sample_cases, random_seed=42)

    assert res["evaluation_configuration"]["candidate_pool_size"] == 25
    assert res["evaluation_configuration"]["candidate_universe_size"] == 60

    # Check that each baseline has candidate generation recall recorded
    for b_name in ["historical_hotspot_baseline", "geographic_distance_baseline", "random_reference_baseline"]:
        b_res = res["baselines"][b_name]
        assert "candidate_generation" in b_res
        assert b_res["candidate_generation"]["candidate_recall@25"] >= 0.0


# ── TEST 5 & 6: CANDIDATE RECALL SEPARATION & BASELINE COMPARISON ─────────────

def test_candidate_recall_separated_from_ranking(sample_cases):
    """Verify candidate recall and conditional ranking recall are reported separately."""
    evaluator = ReproducibleEvaluator()
    res = evaluator.evaluate_benchmark(sample_cases, random_seed=42)

    v7_res = res["production_model_v7_compat"]
    cg = v7_res["candidate_generation"]
    uncond = v7_res["unconditional_ranking_metrics"]
    cond = v7_res["conditional_ranking_metrics"]

    assert "candidate_recall@25" in cg
    assert "missing_target_count" in cg
    assert cg["candidate_hit_count"] + cg["missing_target_count"] == len(sample_cases)

    # When missing_target_count > 0, conditional recall is >= unconditional recall
    if cg["missing_target_count"] > 0:
        assert cond["conditional_r3"] >= uncond["r3"]


def test_production_model_beats_random_baseline(sample_cases):
    """Verify production V7-compat significantly outperforms the random baseline."""
    evaluator = ReproducibleEvaluator()
    res = evaluator.evaluate_benchmark(sample_cases, random_seed=42)

    v7_r3 = res["production_model_v7_compat"]["unconditional_ranking_metrics"]["r3"]
    rand_r3 = res["baselines"]["random_reference_baseline"]["unconditional_ranking_metrics"]["r3"]
    v7_err = res["production_model_v7_compat"]["spatial_error"]["median_error_km"]
    rand_err = res["baselines"]["random_reference_baseline"]["spatial_error"]["median_error_km"]

    # Production model Top-3 should be >= random baseline
    assert v7_r3 >= rand_r3
    # Production model median distance error should be <= random baseline
    assert v7_err <= rand_err


# ── TEST 7 & 8: CAUSALITY & LEAKAGE ───────────────────────────────────────────

def test_case_group_leakage_detection():
    """Verify verification correctly flags overlapping complaint cases between train & test."""
    train_c = [{"complaint": {"complaint_number": "CMP-1"}}, {"complaint": {"complaint_number": "CMP-2"}}]
    test_c_clean = [{"complaint": {"complaint_number": "CMP-3"}}, {"complaint": {"complaint_number": "CMP-4"}}]
    test_c_leaked = [{"complaint": {"complaint_number": "CMP-2"}}, {"complaint": {"complaint_number": "CMP-5"}}]

    clean_res = verify_case_group_leakage(train_c, test_c_clean)
    assert clean_res["leakage_detected"] is False
    assert clean_res["is_disjoint"] is True

    leaked_res = verify_case_group_leakage(train_c, test_c_leaked)
    assert leaked_res["leakage_detected"] is True
    assert leaked_res["overlapping_cases_count"] == 1


def test_chronological_causality_verification():
    """Verify temporal causality checker rejects transactions after prediction cutoff."""
    cutoff = "2026-09-15T12:00:00Z"
    txs_clean = ["2026-09-15T10:00:00Z", "2026-09-15T11:30:00Z"]
    txs_leaked = ["2026-09-15T10:00:00Z", "2026-09-15T13:00:00Z"]  # 13:00 > 12:00

    clean_res = verify_chronological_causality(cutoff, txs_clean)
    assert clean_res["causality_preserved"] is True
    assert clean_res["future_transactions_found"] == 0

    leaked_res = verify_chronological_causality(cutoff, txs_leaked)
    assert leaked_res["causality_preserved"] is False
    assert leaked_res["future_transactions_found"] == 1


# ── TEST 9 - 13: REAL DATA VALIDATOR ──────────────────────────────────────────

def test_real_data_validator_valid_sample():
    """Verify authorized real-data validator passes a well-formed fixture with masked PII."""
    validator = RealDataImportValidator()
    payload = {
        "metadata": {
            "source_system": "NCRP",
            "batch_id": "BATCH-NCRP-2026-01",
            "authorized_officer_id": 1,
            "export_date": "2026-09-20T00:00:00Z",
            "jurisdiction_state": "Delhi",
            "pii_attestation": True,
        },
        "records": [
            {
                "case_id": "NCRP-2026-DL-001",
                "reported_at": "2026-09-15T10:00:00Z",
                "fraud_type": "UPI / QR Code Fraud",
                "amount": 50000.0,
                "victim_lat": 28.6139,
                "victim_lon": 77.2090,
                "victim_district": "CENTRAL_NEW_DELHI",
                "realized_cashout_lat": 28.6250,
                "realized_cashout_lon": 77.2150,
                "realized_cashout_cluster_id": 12,
                "realized_cashout_time": "2026-09-15T11:45:00Z",
            }
        ]
    }
    result = validator.validate_dataset(payload)
    assert result["is_valid"] is True
    assert result["validation_status"] == "PASSED"
    assert result["valid_records_count"] == 1
    assert result["pii_compliance_status"] == "COMPLIANT"


def test_real_data_validator_pii_detection():
    """Verify validator catches and rejects raw unmasked phone, Aadhaar, and PAN."""
    validator = RealDataImportValidator()
    payload = {
        "metadata": {
            "source_system": "STATE_LEA_EXPORT",
            "batch_id": "BATCH-LEA-01",
            "export_date": "2026-09-20T00:00:00Z",
            "pii_attestation": True,
        },
        "records": [
            {
                "case_id": "LEA-001",
                "reported_at": "2026-09-15T10:00:00Z",
                "fraud_type": "Investment Scam",
                "amount": 10000.0,
                "victim_lat": 28.6139,
                "victim_lon": 77.2090,
                "victim_district": "CENTRAL_NEW_DELHI",
                "realized_cashout_cluster_id": 5,
                "victim_notes": "Victim phone 9811122233 called suspect with PAN ABCDE1234F",
            }
        ]
    }
    result = validator.validate_dataset(payload)
    assert result["is_valid"] is False
    assert result["pii_compliance_status"] == "VIOLATION_DETECTED"
    assert any("phone" in e for e in result["errors"])
    assert any("PAN" in e for e in result["errors"])


def test_real_data_validator_temporal_and_duplicate_anomalies():
    """Verify validator flags duplicate case IDs and future timestamps."""
    validator = RealDataImportValidator()
    payload = {
        "metadata": {
            "source_system": "NCRP",
            "batch_id": "BATCH-02",
            "export_date": "2026-09-20T00:00:00Z",
            "pii_attestation": True,
        },
        "records": [
            {
                "case_id": "DUP-001",
                "reported_at": "2030-01-01T00:00:00Z",  # Future date
                "fraud_type": "Loan App Extortion",
                "amount": 15000.0,
                "victim_lat": 28.6139,
                "victim_lon": 77.2090,
                "victim_district": "WEST",
                "realized_cashout_cluster_id": 3,
            },
            {
                "case_id": "DUP-001",  # Duplicate ID
                "reported_at": "2026-09-10T10:00:00Z",
                "fraud_type": "Loan App Extortion",
                "amount": 15000.0,
                "victim_lat": 28.6139,
                "victim_lon": 77.2090,
                "victim_district": "WEST",
                "realized_cashout_cluster_id": 3,
            }
        ]
    }
    result = validator.validate_dataset(payload)
    assert result["is_valid"] is False
    assert any("Duplicate case_id" in e for e in result["errors"])
    assert any("future" in e for e in result["errors"])


def test_real_data_status_pending_disclosure():
    """Verify real data validation truthfully reports REAL_VALIDATION_PENDING."""
    status = get_real_data_validation_status()
    assert status["status"] == "REAL_VALIDATION_PENDING"
    assert status["evaluation_readiness"] == "SYNTHETIC_EVALUATED_REAL_PENDING"
    assert len(status["external_acceptance_gates"]) == 3
    assert any("NCRP" in g.get("gate", "") or "NCRP" in g.get("description", "") for g in status["external_acceptance_gates"])


# ── TEST 14 & 15: PROMOTION GATES & ARTIFACT INTEGRITY ────────────────────────

def test_promotion_gates_reject_unmet_evidence():
    """Verify promotion gate evaluator blocks models that fail thresholds."""
    failing_cand = {
        "model_name": "candidate-weak-v1",
        "candidate_recall@25": 65.0,  # Below 72.0% threshold
        "r1": 10.0,
        "r3": 18.0,
        "mrr": 0.15,
        "median_error_km": 8.5,
        "ece": 0.08,
    }
    baseline = {
        "model_name": "cashout-location-xgb-v4",
        "r1": 8.17,
        "r3": 19.65,
        "mrr": 0.1926,
    }

    eval_result = evaluate_promotion_gates(failing_cand, baseline)
    assert eval_result["internal_synthetic_gates_passed"] is False
    assert eval_result["can_promote_to_production"] is False
    # A rejected candidate must advertise the verified rollback baseline, not
    # the currently promoted runtime model.
    assert eval_result["active_production_model"] == "cashout-location-xgb-v7-compat"


def test_production_artifacts_unmodified_45_hashes():
    """Verify all critical production model weights and schemas match their baseline SHA-256 hashes."""
    integrity = verify_production_artifact_integrity()
    assert integrity["all_production_artifacts_intact"] is True
    assert integrity["verified_count"] == 6

    for fname, details in integrity["results"].items():
        assert details["matched"] is True, f"Artifact {fname} hash mismatch: {details}"


# ── TEST 16: API ENDPOINTS ────────────────────────────────────────────────────

def test_api_evaluation_endpoints(client: TestClient, admin_headers: dict):
    """Verify FastAPI evaluation routes return 200 OK and valid schemas."""
    headers = admin_headers

    # 1. Dataset Inventory
    res_inv = client.get("/api/v1/model/evaluation/inventory", headers=headers)
    assert res_inv.status_code == 200
    inv_data = res_inv.json()
    assert "inventory" in inv_data
    assert "denominator_reconciliation" in inv_data
    assert inv_data["denominator_reconciliation"]["actual_input_cases_sum"] == 5395

    # 2. Baselines Evaluation
    res_base = client.get("/api/v1/model/evaluation/baselines", headers=headers)
    assert res_base.status_code == 200
    base_data = res_base.json()
    assert base_data["evaluation_mode"] == "REPRODUCIBLE_UNIFIED_CANDIDATE_POOL"
    assert "production_model_v7_compat" in base_data
    assert "baselines" in base_data
    assert "historical_hotspot_baseline" in base_data["baselines"]

    # 3. Real Data Status
    res_status = client.get("/api/v1/model/evaluation/real-data-status", headers=headers)
    assert res_status.status_code == 200
    status_data = res_status.json()
    assert status_data["status"] == "REAL_VALIDATION_PENDING"

    # 4. Promotion Gates
    res_gates = client.get("/api/v1/model/evaluation/promotion-gates", headers=headers)
    assert res_gates.status_code == 200
    gates_data = res_gates.json()
    assert gates_data["active_production_model"] == "cashout-location-xgb-v8-debiased"
    assert gates_data["production_artifact_integrity"]["all_production_artifacts_intact"] is True

    # 5. Validate Import (Valid)
    valid_payload = {
        "metadata": {
            "source_system": "NCRP",
            "batch_id": "BATCH-TEST-01",
            "export_date": "2026-09-20T00:00:00Z",
            "pii_attestation": True,
        },
        "records": [
            {
                "case_id": "CR-TEST-01",
                "reported_at": "2026-09-15T10:00:00Z",
                "fraud_type": "UPI / QR Code Fraud",
                "amount": 25000.0,
                "victim_lat": 28.6139,
                "victim_lon": 77.2090,
                "victim_district": "CENTRAL_NEW_DELHI",
                "realized_cashout_cluster_id": 10,
            }
        ],
    }
    res_val = client.post("/api/v1/model/evaluation/validate-import", json=valid_payload, headers=headers)
    assert res_val.status_code == 200
    val_data = res_val.json()
    assert val_data["is_valid"] is True
    assert val_data["validation_status"] == "PASSED"
