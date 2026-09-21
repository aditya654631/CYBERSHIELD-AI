# Phase 10 Handoff: Reproducible Location-Model Evaluation and Data Readiness

**Phase:** 10  
**Problem-statement mapping:** PS-03, PS-04, PS-05, PS-06, PS-07, PS-25  
**Dependencies:** Phases 01, 02, 09  
**Execution date:** 21 September 2026  
**Status:** Completed end-to-end. Programmatic dataset inventory, denominator reconciliation (5,395 actual records vs `combined_6000` label), reproducible evaluation comparing production model against Historical-Hotspot, Geographic Distance, and Random Reference baselines on the exact same candidate universe (K=25), candidate recall separated from ranking recall, case-group and chronological causality leakage tests, authorized real-data import validator with PII detection, truthful `REAL_VALIDATION_PENDING` status for absent real data, predeclared model promotion gates with experiment isolation, and 100% preservation of all 45 production artifact hashes. All 56 test cases pass with exit code 0. Frontend builds cleanly with zero errors. Phase 11 has not started.

---

## 1. Executive Summary & Outcomes

Phase 10 establishes scientific rigor, honest operational benchmarking, and verifiable data readiness for CyberShield AI's predictive cashout location models. Prior to Phase 10, offline evaluation metrics were preserved in static JSON summaries without unified baseline comparisons or candidate-generator recall decomposition, and historical denominator rounding created perceived inconsistencies between report section labels and underlying record counts.

Under Phase 10:
1. **Programmatic Dataset Inventory:**
   - Programmatically catalogues dataset generators (`synthetic_generator.py`, `generate_delhi_v6_*_dataset.py`), exact row and case counts, source provenance, candidate universe (60 Delhi clusters), candidate generation budget (Top-25), target definitions (`realized_cashout_cluster_id`), and feature contracts (47 features: 43 base multimodal location features + 4 V4 compatibility features).
2. **Denominator Reconciliation:**
   - Reconciles the documented discrepancy in `ml/evaluation/v7_compat_external_qualification.json`: the actual input record counts from the three evaluated holdouts (`legacy_seed_56261` with 1,395 cases, `v6_2_seed_56262` with 2,000 cases, and `v6_3_seed_56263` with 2,000 cases) sum exactly to **5,395 cases**. The section label `"combined_6000"` reflected a rounded nominal batch target. All metrics inside the section are mathematically exact over the 5,395 cases.
3. **Reproducible Multi-Baseline Evaluation Framework:**
   - Implemented a unified evaluation entry point (`ml/evaluation/reproducible_evaluator.py`) that evaluates all models and baselines on the **exact same candidate pool (K=25)** generated per case:
     - **Production Model (`cashout-location-xgb-v7-compat`)**: Stacked pairwise ranker over V4 with Platt calibration.
     - **Historical-Hotspot Baseline**: Ranks candidates purely by historical cashout frequency and cluster risk prior.
     - **Geographic Distance Baseline**: Ranks candidates purely by proximity to victim / reporting origin.
     - **Random Reference Baseline**: Uniform random ranking across the candidate pool.
4. **Candidate-Generation Recall vs. Ranking Recall Separation:**
   - Missing target clusters are never concealed by ranking metrics. The framework separately measures:
     - `candidate_recall@25`: % of cases where true cashout cluster is present in candidate pool.
     - `missing_target_count`: count and percentage of cases omitted by candidate generation.
     - `conditional_ranking_recall@k`: Ranker performance evaluated *only* on cases where the target was present in the candidate pool.
     - `unconditional_ranking_recall@k`: End-to-end system recall across all cases.
5. **Statistical Uncertainty & Calibration Disclosures:**
   - Reports 95% Bootstrap Confidence Intervals for Top-1, Top-3, Top-5 accuracy and median distance error.
   - Explicitly discloses that Platt scaling on candidate pairs calibrates relative candidate ranking probabilities, **not** per-case real-world probability of occurrence.
6. **Chronological & Group Leakage Guardrails:**
   - Verified that training, tuning, and evaluation sets remain strictly disjoint.
   - Case-group leakage verification ensures related cases and syndicate incident clusters never cross train/test boundaries.
   - Chronological causality verification ensures feature extraction uses only evidence timestamped prior to prediction cutoff.
7. **Authorized Real-Data Import Validator:**
   - Implemented `RealDataImportValidator` checking schema, source agency (`NCRP`, `CFCFRMS`, `STATE_LEA_EXPORT`), temporal sequence, geographic coordinates within Indian territory, deduplication, missing values, and unmasked PII (rejection of raw phone numbers, Aadhaar, PAN, and card numbers).
   - If real data is absent, the system truthfully returns `REAL_VALIDATION_PENDING` with documented external blocker gates. No real cybercrime or bank records are fabricated.
8. **Predeclared Promotion Gates & Experiment Isolation:**
   - Formalized promotion gates (Candidate Recall >= 72%, Top-3 Lift >= V4 + 3.0pp, Spatial Error <= 6.0km, ECE <= 0.05, Latency <= 100ms, Real-Data Validation Gate).
   - Enforced that experiments are isolated under `ml/experiments/` and cannot overwrite `ml/artifacts/`.
   - The authoritative production model `cashout-location-xgb-v7-compat` remains unchanged. All 45 baseline artifact SHA-256 hashes match 100%.

---

## 2. Before and After Comparison

| Capability | Before Phase 10 | After Phase 10 |
|---|---|---|
| **Dataset Inventory** | Dispersed across JSON manifests and training scripts. | Programmatic unified inventory (`dataset_inventory.py`) exposing case counts, schemas, and candidate universe. |
| **Denominator Accuracy** | Labeled as `"combined_6000"` despite 5,395 input records. | Programmatically reconciled (5,395 actual records, discrepancy explained, exact denominators reported). |
| **Baseline Comparisons** | Compared primarily against V4 baseline. | Unified evaluation against Historical-Hotspot, Geographic Distance, and Random Reference baselines on identical candidate pools. |
| **Candidate Recall Separation** | Candidate recall and ranking recall were partially entangled. | Explicit separation of `candidate_recall@25`, `missing_target_count`, conditional ranking recall, and unconditional recall. |
| **Statistical Uncertainty** | Point estimates without confidence bounds. | 95% Bootstrap Confidence Intervals computed for Top-k accuracy and distance error. |
| **Leakage Verification** | Implicit chronological assumptions. | Formal verification functions for case-group leakage and chronological causality. |
| **Real-Data Readiness** | No ingestion validator or PII safeguards for external data. | `RealDataImportValidator` enforcing schema, provenance, temporal order, bounds, and PII masking. |
| **Real-Data Status** | Ambiguous external readiness state. | Truthful `REAL_VALIDATION_PENDING` status with documented external blocker gates. |
| **Promotion Governance** | Informal criteria. | Predeclared formal promotion gates, experiment quarantine under `ml/experiments/`, and immutable production artifacts. |

---

## 3. Implementation Details

### ML Evaluation Modules
- **`ml/evaluation/dataset_inventory.py`:**
  - `get_dataset_inventory()`: Programmatic catalog of legacy V2 and expanded multi-regime training datasets.
  - `get_feature_inventory()`: Canonical 47-feature list (43 base + 4 V4 compat).
  - `get_candidate_universe_inventory()`: Delhi 60-cluster universe and K=25 candidate generator configuration.
  - `reconcile_saved_denominators()`: Audits `v7_compat_external_qualification.json` and reconciles the 5,395 actual cases against the `combined_6000` label.
- **`ml/evaluation/reproducible_evaluator.py`:**
  - `ReproducibleEvaluator`: Single entry point executing on identical K=25 candidate pools.
  - `score_candidates_hotspot`: Historical cashout frequency baseline.
  - `score_candidates_distance`: Spatial proximity to victim baseline.
  - `score_candidates_random`: Seeded pseudo-random reference baseline.
  - `evaluate_model_predictions`: Calculates candidate recall, missing targets, conditional and unconditional ranking recall, MRR, distance error, and 95% bootstrap CIs.
  - `verify_case_group_leakage`: Detects cross-split complaint/case overlap.
  - `verify_chronological_causality`: Verifies evidence timestamps precede prediction cutoffs.
- **`ml/evaluation/real_data_validator.py`:**
  - `RealDataImportValidator`: Ingestion validator checking schema, authorized provenance, date ordering, Indian geographic bounds, duplicate IDs, missing values, and PII patterns (phone, Aadhaar, PAN, card numbers).
  - `get_real_data_validation_status()`: Truthful `REAL_VALIDATION_PENDING` reporting.
- **`ml/evaluation/promotion_gates.py`:**
  - `evaluate_promotion_gates()`: Assesses candidates against predeclared gates.
  - `verify_production_artifact_integrity()`: Validates production core hashes in `ml/artifacts/`.
  - `get_isolated_experiment_dir()`: Quarantines experimental runs under `ml/experiments/`.

### Backend API Integration
- **`backend/app/schemas/schemas.py`:**
  - Added `RealDataImportMetadata`, `RealDataImportValidationRequest`, `RealDataImportValidationResponse`, `RealDataValidationStatusResponse`.
- **`backend/app/api/model_routes.py`:**
  - `GET  /api/v1/model/evaluation/inventory`: Dataset inventory and reconciled denominators.
  - `GET  /api/v1/model/evaluation/baselines`: Reproducible evaluation comparing production model vs hotspot vs distance vs random.
  - `GET  /api/v1/model/evaluation/real-data-status`: Truthful `REAL_VALIDATION_PENDING` status.
  - `POST /api/v1/model/evaluation/validate-import`: Validates external dataset payloads.
  - `GET  /api/v1/model/evaluation/promotion-gates`: Predeclared promotion gates and artifact verification.

### Frontend Compilation Fix
- **`frontend/src/pages/OutcomeMetrics.tsx`:**
  - Resolved TypeScript interface-vs-component naming collision by importing `OutcomeMetrics as OutcomeMetricsType`.
  - `npm run build` exits with code 0.

---

## 4. Verification & Test Results

### Test Suite Execution
Targeted Phase 10 test suite (`tests/test_phase10_model_evaluation.py`) plus Phase 09, Phase 04, and model verification regression suites:

```
============================= test session starts =============================
platform win32 -- Python 3.13.0, pytest-9.1.1, pluggy-1.6.0
collected 56 items

tests/test_phase10_model_evaluation.py::test_dataset_inventory_metadata PASSED [  1%]
tests/test_phase10_model_evaluation.py::test_denominator_reconciliation PASSED [  3%]
tests/test_phase10_model_evaluation.py::test_reproducible_evaluation_fixed_seed PASSED [  5%]
tests/test_phase10_model_evaluation.py::test_baselines_comparable_candidate_universe PASSED [  7%]
tests/test_phase10_model_evaluation.py::test_candidate_recall_separated_from_ranking PASSED [  8%]
tests/test_phase10_model_evaluation.py::test_production_model_beats_random_baseline PASSED [ 10%]
tests/test_phase10_model_evaluation.py::test_case_group_leakage_detection PASSED [ 12%]
tests/test_phase10_model_evaluation.py::test_chronological_causality_verification PASSED [ 14%]
tests/test_phase10_model_evaluation.py::test_real_data_validator_valid_sample PASSED [ 16%]
tests/test_phase10_model_evaluation.py::test_real_data_validator_pii_detection PASSED [ 17%]
tests/test_phase10_model_evaluation.py::test_real_data_validator_temporal_and_duplicate_anomalies PASSED [ 19%]
tests/test_phase10_model_evaluation.py::test_real_data_status_pending_disclosure PASSED [ 21%]
tests/test_phase10_model_evaluation.py::test_promotion_gates_reject_unmet_evidence PASSED [ 23%]
tests/test_phase10_model_evaluation.py::test_production_artifacts_unmodified_45_hashes PASSED [ 25%]
tests/test_phase10_model_evaluation.py::test_api_evaluation_endpoints PASSED [ 26%]
tests/test_phase9_outcome_observations.py::test_confirmed_cashout_creates_outcome PASSED [ 28%]
tests/test_phase9_outcome_observations.py::test_unknown_outcome_no_prediction_required PASSED [ 30%]
tests/test_phase9_outcome_observations.py::test_invalid_outcome_type_rejected PASSED [ 32%]
tests/test_phase9_outcome_observations.py::test_excluded_without_reason_rejected PASSED [ 33%]
tests/test_phase9_outcome_observations.py::test_multiple_cashout_stores_cashout_events PASSED [ 35%]
tests/test_phase9_outcome_observations.py::test_multiple_cashout_partial_amounts_stored_separately PASSED [ 37%]
tests/test_phase9_outcome_observations.py::test_no_future_prediction_linked PASSED [ 39%]
tests/test_phase9_outcome_observations.py::test_historical_replay_prediction_excluded PASSED [ 41%]
tests/test_phase9_outcome_observations.py::test_last_operational_before_event_selected PASSED [ 42%]
tests/test_phase9_outcome_observations.py::test_correction_creates_new_version PASSED [ 44%]
tests/test_phase9_outcome_observations.py::test_correction_of_superseded_record_rejected PASSED [ 46%]
tests/test_phase9_outcome_observations.py::test_correction_without_reason_rejected PASSED [ 48%]
tests/test_phase9_outcome_observations.py::test_unknown_excluded_from_measured_denominator PASSED [ 50%]
tests/test_phase9_outcome_observations.py::test_synthetic_cohort_separate PASSED [ 51%]
tests/test_phase9_outcome_observations.py::test_data_excluded_counted_separately PASSED [ 53%]
tests/test_phase9_outcome_observations.py::test_metrics_returns_none_rates_when_no_cashouts PASSED [ 55%]
tests/test_phase9_outcome_observations.py::test_held_and_recovered_stored_separately PASSED [ 57%]
tests/test_phase9_outcome_observations.py::test_metrics_financial_note_present PASSED [ 58%]
tests/test_phase9_outcome_observations.py::test_metrics_financials_reported_as_separate_keys PASSED [ 60%]
tests/test_phase9_outcome_observations.py::test_analyst_cannot_ingest_outcome PASSED [ 62%]
tests/test_phase9_outcome_observations.py::test_auditor_cannot_ingest_outcome PASSED [ 64%]
tests/test_phase9_outcome_observations.py::test_state_lea_can_ingest_outcome PASSED [ 66%]
tests/test_phase9_outcome_observations.py::test_analyst_can_read_metrics PASSED [ 67%]
tests/test_phase9_outcome_observations.py::test_ingest_and_retrieve_outcome PASSED [ 69%]
tests/test_phase9_outcome_observations.py::test_list_outcomes_for_complaint PASSED [ 71%]
tests/test_phase9_outcome_observations.py::test_correct_outcome_via_api PASSED [ 73%]
tests/test_phase4_model_performance.py::test_endpoint_authorization_gate PASSED [ 75%]
tests/test_phase4_model_performance.py::test_trained_runtime_with_matching_v7_metadata PASSED [ 76%]
tests/test_phase4_model_performance.py::test_trained_runtime_with_missing_evaluation_metadata PASSED [ 78%]
tests/test_phase4_model_performance.py::test_explicit_demo_runtime PASSED [ 80%]
tests/test_phase4_model_performance.py::test_failed_model_loading_and_error_sanitization PASSED [ 82%]
tests/test_phase4_model_performance.py::test_metadata_for_wrong_model_version PASSED [ 83%]
tests/test_phase4_model_performance.py::test_benchmark_comparability_truthfulness PASSED [ 85%]
tests/test_phase4_model_performance.py::test_research_models_governance PASSED [ 87%]
tests/test_phase4_model_performance.py::test_saved_prediction_provenance_card PASSED [ 89%]
tests/test_phase4_model_performance.py::test_artifact_hash_mismatch_rejection PASSED [ 91%]
tests/test_phase4_model_performance.py::test_legitimate_zero_metrics_preserved PASSED [ 92%]
tests/test_phase4_model_performance.py::test_no_percentage_double_conversion PASSED [ 94%]
tests/test_model_verification.py::test_model_verification_official_artifacts PASSED [ 96%]
tests/test_model_verification.py::test_model_verification_missing_metadata PASSED [ 98%]
tests/test_model_verification.py::test_compute_sha256_missing_file PASSED [100%]

======================== 56 passed in 126.56s (0:02:06) ========================
```

### Frontend Production Build
```
> cd frontend && npm run build
✓ 2505 modules transformed.
✓ built in 35.75s (exit code 0)
```

### Baseline Artifact Hash Preservation (All 45 Files Matched 100%)
All 45 baseline artifact files in `ml/artifacts/` were verified against `scratch/phase0_20260917T175141Z/baseline.json`:
- `location_ranker_v7_compat.joblib`: `89057bce1000cb82e10f29077b9e168bc0cbd254e979106998e1d623e072c2a6` (MATCH)
- `location_calibrator_v7_compat.joblib`: `1c14d5aba1b0556a47519ea435804a86b34173c76743a77bcf52cea43d3a2c6d` (MATCH)
- `model_metadata_v7_compat.json`: `d402ab6c397327fbce5916621e1da51766ee87b7a5449fa152c0e969b10c59f4` (MATCH)
- `feature_schema_v7_compat.json`: `fc303d7e8b995e1a9903706d4a7da21431c8424e27edf30b4757f900f7642444` (MATCH)
- `location_ranker_v4.joblib`: `9ed5792ced4f8a6e79dc91e587e3c130d2fbadb5af6a73640397dc506dd9cdc9` (MATCH)
- `location_calibrator_v4.joblib`: `65ceb736838d14cb865111aac6eddfad3838704ddf2fffc63a6b2bdd998a3664` (MATCH)
- All remaining 39 artifacts: **100% MATCH (0 retrained, 0 drifted)**.

### Checksums of Phase 10 Files (SHA-256)
| File | SHA-256 Hash |
|---|---|
| `ml/evaluation/dataset_inventory.py` | `BF9C6D9BD2A2FBBA32E98E54F9E874C3B44000E967C6F37E996D8EA20DF8C2A7` |
| `ml/evaluation/reproducible_evaluator.py` | `D033C245A39396E3790A1FCA04145B7EF49A99E7BE59F674272A15CB4E941C9E` |
| `ml/evaluation/real_data_validator.py` | `2A62A5C53D4B388E9A66EA94C8330B8EC88709D6D8670BC0DE97D252DDCF62E1` |
| `ml/evaluation/promotion_gates.py` | `19349A2BF66A9F842479165AC5E986330052AFCB1C408404E6721FF99CF770F2` |
| `backend/app/schemas/schemas.py` | `5BEDDC5B947AA6D65F3878A10A8B8513C8CDBBEC08983E38555688A35D470307` |
| `backend/app/api/model_routes.py` | `4051C4B31266104A7F031718BFDA8D49EA17B7433408A4BEDF04A5F50891F6D3` |
| `frontend/src/pages/OutcomeMetrics.tsx` | `19CB98AAB2FD01A943DE9117D0714B25EF76E760767851B34AB9F0265C80C3E7` |
| `tests/test_phase10_model_evaluation.py` | `C6CCF7C47274571547E39CF1B3DF0CE35787CB7910525218F5E257D4290146E8` |

---

## 5. Pending External Gates & Rollback Procedure

### Pending External Gates
1. **GATE_NCRP_PARTNER_CREDENTIALS:** Formal MoU and extraction credentials for live National Cybercrime Reporting Portal data.
2. **GATE_CFCFRMS_BANK_INTEGRATION:** Direct API integration with partner bank core systems and CFCFRMS data feeds.
3. **GATE_STATE_LEA_OUTCOME_AUDIT:** Multi-state operational field cashout seizure outcome logs for external validation.

### Rollback Procedure
If rollback of Phase 10 is required:
1. Revert changes to `backend/app/api/model_routes.py` and `backend/app/schemas/schemas.py` via Git.
2. Delete the new evaluation modules: `ml/evaluation/dataset_inventory.py`, `ml/evaluation/reproducible_evaluator.py`, `ml/evaluation/real_data_validator.py`, `ml/evaluation/promotion_gates.py`, and `tests/test_phase10_model_evaluation.py`.
3. Re-verify the 45 artifact hashes in `ml/artifacts/` using `scripts/phase0_audit.py`.

---

**Execution Halted**: Phase 10 is complete and verified. Phase 11 has not started.
