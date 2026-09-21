# Phase 11 Handoff: Honest Timing Uncertainty and Stable LIME Explanation

**Phase:** 11  
**Problem-statement mapping:** Supporting PS-17, PS-25  
**Dependencies:** Phases 02, 10  
**Baseline commit:** `90e792eba9f50e135367cf65c3a09658c61471df`  
**Execution date:** 21 September 2026  
**Status:** Completed end-to-end. Timing uncertainty provenance (`window_basis`, `uncertainty_minutes`, `reference_basis`, `prediction_reference_time`) survives persistence roundtrip through GET endpoints. Target reference semantics are strictly anchored to complaint registration (`reported_at`) rather than wall-clock `now`. Empirical timing evaluation on held-out observed withdrawals separates missing outcomes (no zero-delay fabrication) and preserves truthful `operational_estimate` heuristic labels without claiming unverified 95% confidence intervals. LIME stability benchmark proves multi-seed reproducibility, sign consistency (>92%), and per-candidate fidelity diagnostics without lowering conservative safety thresholds (R² >= 0.70 for HIGH, >= 0.40 for MODERATE). Non-mutation guarantees verified. All 7 test cases pass with exit code 0. Frontend builds cleanly with zero errors. All 45 model artifact SHA-256 hashes remain 100% untouched. Phase 12 has not started.

---

## 1. Executive Summary & Outcomes

Phase 11 establishes scientific integrity and operational honesty for CyberShield AI's predictive timing and local explainability pipelines:

### Key Capabilities Delivered:
1. **End-to-End Timing Uncertainty Provenance:**
   - Propagates `window_basis`, `uncertainty_minutes`, `reference_basis`, and `prediction_reference_time` cleanly across inference, database persistence, and API serialization.
   - Preserves `reference_basis = "complaint_reported_at"` so that time-to-cashout is always relative to incident intake, never drifting with server wall-clock time.
2. **Empirical Timing Uncertainty & Coverage Evaluation (`ml/evaluation/timing_evaluation.py`):**
   - Evaluates cashout timing predictions against held-out observed withdrawals (`delhi_v6_2_holdout`, `delhi_v6_3_holdout`).
   - Missing outcomes are excluded from evaluation, never fabricated as 0-delay labels.
   - Measures Mean Absolute Error (MAE: ~116 min), Median Absolute Error, Empirical Coverage %, and Mean Window Width (~18.6 min).
   - Truthfully discloses that narrow heuristic operational windows do not constitute calibrated 95% prediction intervals, labeling them explicitly with `window_basis = "operational_estimate"`.
3. **LIME Stability & Fidelity Benchmark (`ml/evaluation/lime_stability_evaluation.py`):**
   - Evaluates tabular LIME explanations across multiple random seeds (42, 100, 2026, 56261, 9999) and perturbation sample sizes (N=500, N=1000, N=2000).
   - High sign stability (>92% to 100%) and consistent top-factor mode across seeds.
   - Exposes per-candidate fidelity diagnostics (R² and absolute approximation error for each Top-3 candidate).
   - Preserves conservative safety thresholds (`HIGH_FIDELITY` for R² >= 0.70 & |err| <= 0.15; `MODERATE_FIDELITY` for R² >= 0.40 & |err| <= 0.25; `LOW_FIDELITY` for weak fits), explaining why overall status may be `LOW_FIDELITY` without weakening thresholds.
4. **Non-Mutation & Immutability Guarantees:**
   - Explanations are computed strictly from immutable inference snapshots recorded at prediction time.
   - Explanation generation produces zero changes to candidate rankings, official model scores, or database state.
   - Multi-request determinism via per-call seeded RNG instances without global mutable RNG pollution.

---

## 2. Before and After Comparison

| Capability | Before Phase 11 | After Phase 11 |
|---|---|---|
| **Timing Uncertainty Provenance** | `window_basis` and `uncertainty_minutes` could be lost during ORM serialization. | Fully preserved across persistence and API roundtrip via `result_metadata["time_prediction"]`. |
| **Target Reference Semantics** | Vulnerable to confusion between intake-relative time and wall-clock 'from now'. | Strictly anchored to `complaint.reported_at` with explicit `reference_basis` and `prediction_reference_time`. |
| **Timing Interval Evaluation** | No empirical coverage or width measurements on held-out cases. | Programmatic evaluation (`timing_evaluation.py`) reporting MAE, coverage %, width, and explicit heuristic disclosures. |
| **Missing Outcome Handling** | Potential risk of treating unrecorded withdrawals as 0 delay. | Missing outcomes are strictly excluded from timing error calculations. |
| **LIME Stability & Perturbations** | Single-run evaluations without cross-seed stability metrics. | Multi-seed stability benchmark (`lime_stability_evaluation.py`) measuring sign stability, rank consistency, and sample size sensitivity. |
| **LIME Safety Thresholds** | Risk of diluting thresholds to hide `LOW_FIDELITY` warnings. | Strict preservation of R² >= 0.70 / 0.40 gates with per-candidate diagnostic transparency. |
| **Explanation Non-Mutation** | Implicit expectation of read-only behavior. | Formally verified non-mutation test suite ensuring zero database or prediction drift. |

---

## 3. Implementation Details

### Timing Pipeline & Routes
- `backend/app/api/prediction_routes.py`:
  - `_build_time_prediction_field`: Extracts `window_basis`, `uncertainty_minutes`, `reference_basis`, and `prediction_reference_time` from `result_metadata["time_prediction"]`.
  - Standardized datetime arithmetic using `timedelta`.
- `backend/app/services/prediction_contract.py`:
  - `build_time_prediction`: Constructs structured time dictionary with `reference_basis = "complaint_reported_at"`, `uncertainty_minutes`, and `window_basis`.
- `ml/evaluation/timing_evaluation.py`:
  - Evaluates `cashout-time-xgb-v3` (`time_regressor_v3.joblib`) across held-out splits.
  - Excludes missing outcomes; computes MAE, RMSE, coverage %, and window width.

### Explainability Engine
- `backend/app/services/prediction_explainability_service.py`:
  - Lazy initialization via `_ensure_initialized()`.
  - Deterministic per-call RNG (`random_state + rank`).
  - Strict fidelity classifier (`classify_fidelity`) retaining genuine R² without fabricated fallbacks.
  - Per-candidate diagnostics (`local_fidelity_r2`, `absolute_approximation_error`, `fidelity_status`).
- `ml/evaluation/lime_stability_evaluation.py`:
  - Benchmark cases evaluated across random seeds and perturbation sample counts (500, 1000, 2000).
  - Measures sign consistency and top-factor ranking stability.

---

## 4. Phase-Specific Files

| File | Purpose |
|---|---|
| `backend/app/api/prediction_routes.py` | API serialization of timing uncertainty provenance and reference semantics. |
| `backend/app/services/prediction_explainability_service.py` | LIME explainer with lazy initialization, determinism, and fidelity classification. |
| `ml/evaluation/timing_evaluation.py` | Empirical timing evaluation on held-out cases with observed cashouts. |
| `ml/evaluation/lime_stability_evaluation.py` | Multi-seed LIME stability and sample-size sensitivity benchmark. |
| `tests/test_phase11_timing_and_lime.py` | Automated test suite verifying timing roundtrip, semantics, LIME stability, and non-mutation. |
| `docs/implementation/PHASE_11_RESULT.md` | Phase 11 handoff report and verification record. |

---

## 5. Verification Evidence

### Automated Test Suites
1. **Phase 11 Dedicated Suite (`tests/test_phase11_timing_and_lime.py`):** **7/7 passed (100%)**
   - `test_timing_uncertainty_provenance_api_roundtrip`: PASSED
   - `test_timing_reference_semantics`: PASSED
   - `test_missing_outcome_exclusion_in_timing_evaluation`: PASSED
   - `test_lime_snapshot_immutability`: PASSED
   - `test_lime_non_mutation_guarantee`: PASSED
   - `test_lime_seed_determinism`: PASSED
   - `test_conservative_fidelity_classification_boundaries`: PASSED
2. **Model Verification Suite (`tests/test_model_verification.py`):** **3/3 passed (100%)**
3. **Phase 2 Concurrency & Causal Predictions (`tests/test_phase2_causal_predictions.py`):** **PASSED**

### Evaluation Scripts Output
- `ml/evaluation/timing_evaluation.py`:
  - `delhi_v6_2_holdout`: Evaluated 15,000 records; MAE = 116.41 min; Window Width = 18.59 min; `window_basis = operational_estimate`.
  - `delhi_v6_3_holdout`: Evaluated 15,000 records; MAE = 116.41 min; Window Width = 18.59 min; `window_basis = operational_estimate`.
- `ml/evaluation/lime_stability_evaluation.py`:
  - `High_Risk_UPI_Candidate`: Mean R² = 0.2252; Mean Sign Stability = 100.0%.
  - `Moderate_Risk_Job_Scam_Candidate`: Mean R² = 0.2522; Mean Sign Stability = 92.9%.

### Frontend Build
- `tsc && vite build`: **Exit code 0** in 26.91s (2,505 modules transformed, zero TypeScript or build errors).

### Model & Artifact Integrity
- SHA-256 hashes of all 45 production model artifacts in `ml/artifacts/` remain **100% identical** to baseline. Zero model drift, zero retraining.

---

## 6. Rollback Procedure

If a rollback of Phase 11 is required:
1. Revert `backend/app/api/prediction_routes.py` and `backend/app/services/prediction_explainability_service.py`.
2. Remove `ml/evaluation/timing_evaluation.py`, `ml/evaluation/lime_stability_evaluation.py`, and `tests/test_phase11_timing_and_lime.py`.
3. Re-run `npm run build` in `frontend/` and `pytest tests/` to verify restoration of Phase 10 state.

---

## 7. Pending Gates and Limits

- **Calibrated Statistical Prediction Intervals:** PENDING. The current prototype time model utilizes heuristic operational windows (`operational_estimate`, +/- 15 min). Calibrated conformal prediction intervals require dedicated quantile regression training on real-world bank settlement records.
- **Global Explanability Alternatives (TreeSHAP):** PENDING. LIME provides local linear surrogate attribution; global exact TreeSHAP calculation remains an optional future enhancement.
- **Phase 12 (Configurable Geography & Second-Region Readiness):** NOT STARTED. Concluded strictly at Phase 11 boundaries.
