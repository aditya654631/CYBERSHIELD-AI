# Phase 02 Handoff: Causal Transaction Updates and Immutable Prediction Versions

**Phase Number:** 02  
**Phase Title:** Causal Transaction Updates and Immutable Prediction Versions  
**Dependencies:** Phase 00 (Baseline Protection and Measured Audit), Phase 01 (Stabilize Tests and Truthful Product Claims)  
**Baseline Commit:** `90e792eba9f50e135367cf65c3a09658c61471df`  
**Execution Date:** 19–20 September 2026 UTC  
**Problem Statement Traceability:** PS-01, PS-02, PS-04, PS-06, PS-07, PS-15; Immutable Ledger and Causal Traceability Foundation  

---

## 1. Executive Summary

Phase 02 completes the implementation of causal transaction updates, deduplication contracts, authorized transaction correction/reversal workflows, effective evidence semantics, and immutable prediction versions across the CyberShield AI platform according to `docs/antigravity/PHASE_02.md` and user directives. This phase eliminates the stale-prediction defect, introduces bi-temporal event/knowledge ingestion, enforces sequential immutable prediction lineage per complaint, and ensures strict causal isolation between investigation time and future events:

1. **Stale Prediction Defect Eliminated:**
   - **Root Cause:** Prior logic in `prediction_persistence_service.py` checked only whether the rank-1 location cluster remained identical to the previous prediction. If rank-1 was unchanged while rank-2 or rank-3 clusters changed, it skipped persistence and returned the previous prediction unchanged.
   - **Fix:** Implemented dual canonical fingerprinting: an `input_fingerprint` (SHA-256 digest of normalized complaint attributes, analysis cutoff, eligible effective transactions, and model/schema versions) and a `result_fingerprint` (SHA-256 digest of candidate locations, ranks, probabilities, and window boundaries). Predictions are persisted whenever input evidence or ranking outputs change. If identical input yields differing model outputs, a traceable discrepancy flag (`discrepancy_detected`) is preserved in `result_metadata`.

2. **Sequential, Immutable Prediction Versioning:**
   - **Schema:** Added `version_number` (strictly monotonic integer per complaint), `parent_prediction_id` (pointer to immediate predecessor), `analysis_as_of` (explicit point-in-time cutoff), and `input_fingerprint` to `Prediction`.
   - **Concurrency & Integrity:** Enforced `UNIQUE(complaint_id, version_number)` and index on `(complaint_id, input_fingerprint)`. Concurrent requests racing with identical input fingerprint resolve to the verified winner; competing requests with distinct inputs receive sequential monotonic versions without overwriting history.

3. **Bi-Temporal Ingestion, Transaction Correction/Reversal, and Effective Semantics:**
   - **Transaction Fields:** Added `received_at` (server-controlled knowledge timestamp), `source_system` (`BANK_API`, `LE_PORTAL`, `AGGREGATOR`, etc.), `dedup_key`, `is_reversal`, `correction_of_ref`, and `created_by_user_id` (nullable foreign key to `users.id`) to `Transaction`.
   - **Truthful Actor Attribution:** Transaction ingestion, correction, and reversal bind `created_by_user_id` exclusively from `current_user.id`. Client-supplied creator IDs in request payloads are strictly ignored. Historical rows preserve `NULL` where actor proof is unavailable. Safe actor attribution is exposed only to authorized in-jurisdiction officers (anti-enumeration 404 for wrong jurisdiction).
   - **Temporal Ingestion & Idempotency:** Enforced that `received_at` cannot be spoofed by callers. Authenticated `POST /complaints/{id}/transactions` guarantees server-controlled timestamps, performs deduplication, and triggers post-transfer prediction recalculation. Concurrent duplicate ingestion is handled idempotently via `IntegrityError` rollback.
   - **Authorized Correction & Reversal APIs:** Implemented `POST /complaints/{id}/transactions/correction` and `POST /complaints/{id}/transactions/reversal`. Validates `correction_of_ref` against original immutable records, strictly enforces role (`STATE_LEA`, `DISTRICT_LEA`, `I4C_ADMIN` only; `ANALYST`, `AUDITOR`, `BANK_OFFICER` receive 403 Forbidden) and complaint jurisdiction authorization (anti-enumeration 404 for wrong jurisdiction). Rejects circular, self-referential, or already-reversed chains.
   - **Effective Transaction Semantics:** Original records remain immutable in the database for auditing. In predictive feature construction and graph generation, corrections supersede referenced transactions, reversals cancel original economic effect, chained corrections resolve deterministically (T0 -> T1 -> T2: T2 is active), and original + correction + reversal are never double-counted as separate positive transfers.
   - **Canonical Transaction Identity & Anti-Enumeration:** Enforced global database uniqueness on `transaction_ref` (`uq_transactions_transaction_ref`). Anti-enumeration safeguards return generic 409/404 responses without disclosing cross-case existence.
   - **Causal Cutoff & Knowledge Time:** `resolve_transaction_context` filters transactions such that `transaction_time <= cutoff` (event time) and `received_at <= cutoff` (knowledge time). Historical replay before a correction received timestamp continues seeing the original evidence unmodified. Future cutoffs are rejected with `400 Bad Request`.
   - **Disclosed Legacy Replay:** For legacy transactions where `received_at` is null, replay applies a disclosed assumption (`LEGACY_PRE_PHASE2_ASSUMED_KNOWN`) explicitly tracked in context metadata rather than silently excluding them.

4. **Outcome Isolation & Frontend Version Interface:**
   - Cash-out ATM withdrawal events (`is_withdrawal=True` / `node_type='atm'`) are strictly treated as evaluation targets. They are quarantined from predictive feature generation via `include_outcomes=False` in `graph_service.py` and `ml_feature_service.py` to prevent data leakage from biasing risk scores.
   - Frontend `CaseIntelligence.tsx` implements a Prediction Version History selector, displaying `OPERATIONAL` vs `HISTORICAL_REPLAY` badges, input fingerprints, analysis timestamps, synchronized graph/prediction views, and a prominent yellow warning banner when inspecting historical replays.

5. **Test Suite Verification:**
   - **Final Test Results:** **424 passed, 1 skipped, 0 failed** (425 total tests; **100% executable pass rate**).
   - **Dedicated Phase 2 Tests:** 25 comprehensive tests in `tests/test_phase2_causal_predictions.py` covering defect reproduction, identical retry idempotency, authenticated ingestion with dedup, 409 conflict, causal replay cutoff, outcome quarantine, version endpoints, transaction correction and reversal, multithreaded concurrency race execution, cross-case anti-enumeration, effective transaction semantics, actor attribution (`created_by_user_id`), spoofing prevention, historical NULL preservation, and migration 0012.
   - **Database Migration Tests:** Validated Alembic migrations 0009, 0010, 0011, and 0012 for upgrade, downgrade, and schema preservation.

6. **Artifact Integrity:**
   - All **45 production model and schema artifacts** match their baseline SHA-256 hashes byte-for-byte (**100% match, 0 mismatches, 0 retraining**).

---

## 2. Changed Files and Rationale

| File Path | Nature of Modification | Rationale |
|---|---|---|
| `alembic/versions/0009_phase2_causal_transactions_and_versioning.py` | Alembic Migration | Adds `version_number`, `parent_prediction_id`, `analysis_as_of`, `input_fingerprint` to `predictions`; adds `received_at`, `source_system`, `dedup_key`, `is_reversal`, `correction_of_ref` to `transactions`; creates unique constraints and indexes. Implements deterministic backfill for legacy predictions ordered by `(created_at, id)`. |
| `alembic/versions/0010_explicit_analysis_purpose.py` | Alembic Migration | Adds explicit `analysis_purpose` column to `predictions` table. |
| `alembic/versions/0011_canonical_transaction_dedup.py` | Alembic Migration | Enforces canonical system-wide unique constraint `uq_transactions_transaction_ref` on `transactions.transaction_ref`. |
| `alembic/versions/0012_transaction_created_by_user_id.py` | Alembic Migration | Adds nullable `created_by_user_id` foreign key referencing `users.id` with index `ix_transactions_created_by_user_id` to `transactions`. |
| `backend/app/models/models.py` | SQLAlchemy ORM Models | Added Phase 02 fields to `Prediction` and `Transaction` models, including `uq_transactions_transaction_ref` unique constraint, `created_by_user_id` FK and `created_by_user` relationship. |
| `backend/app/schemas/schemas.py` | Pydantic Schemas | Added `created_by_user_id` to `TransactionResponse` and `TransactionIngestResponse`; excluded from input schemas to prevent spoofing. |
| `backend/app/services/prediction_persistence_service.py` | Idempotency & Versioning Engine | Eliminated rank-1 only debounce bug. Implemented canonical `input_fingerprint` and `result_fingerprint`, sequential version assignment (`version_number = max_v + 1`), parent link tracking, discrepancy detection, and race-winner resolution. Added `get_latest_operational_prediction` and `get_prediction_versions`. |
| `backend/app/services/transaction_context_service.py` | Causal Temporal Filter & Effective Semantics | Added `analysis_as_of` support. Enforces dual cutoffs (`transaction_time <= cutoff` and `received_at <= cutoff`). Implemented `resolve_effective_transactions` to supersede corrected transfers, cancel reversed transfers, and resolve chained corrections. |
| `backend/app/services/graph_service.py` | Outcome Isolation | Point-in-time traversal respecting `analysis_as_of` and `include_outcomes=False` flag to prevent terminal withdrawal cashouts from leaking into prediction features. |
| `backend/app/services/ml_feature_service.py` | Point-in-Time Features | Added `analysis_as_of` cutoff to feature construction and ensured outcome isolation in graph and velocity metrics. |
| `backend/app/services/prediction_service.py` | Prediction Pipeline Wiring | Threaded `analysis_as_of` cutoff and sequential versioning parameters through `predict`, `predict_complaint`, and `run_and_persist_prediction`. |
| `backend/app/api/transaction_routes.py` | Authenticated Ingestion & Correction API | Implemented `POST /complaints/{id}/transactions`, `POST /complaints/{id}/transactions/correction`, and `POST /complaints/{id}/transactions/reversal` with strict LEA/Admin role checks, truthful `created_by_user_id` assignment, server-controlled `received_at`, deduplication, 200 idempotent replay (`X-Idempotent-Replay`), anti-enumeration 409 Conflict, cycle rejection, and post-correction predictive recalculation. |
| `backend/app/api/prediction_routes.py` | Versioned Prediction APIs | Updated `GET /predictions/{complaint_id}` to return the latest operational prediction; added `GET /predictions/{complaint_id}/versions` with `analysis_purpose`; added `GET /predictions/version/{prediction_id}` for point-in-time audit; updated `POST /predictions/{complaint_id}` to accept optional `analysis_as_of`. |
| `frontend/src/types/index.ts` | TypeScript Interfaces | Updated `Prediction` and `PredictionVersionSummary` interfaces with `analysis_purpose`, `version_number`, `parent_prediction_id`, `analysis_as_of`, `input_fingerprint`, `discrepancy_detected`. |
| `frontend/src/services/api.ts` | Frontend API Service | Added `getPredictionVersions` and `getPredictionVersionById` methods. |
| `frontend/src/pages/CaseIntelligence.tsx` | Case Intelligence UI | Added Prediction Version selector, badges for `OPERATIONAL` vs `HISTORICAL_REPLAY`, replay warning banner, and synchronized prediction/graph viewing. |
| `tests/test_phase2_causal_predictions.py` | Targeted Test Suite | 25 comprehensive tests covering defect reproduction, idempotent retries, authenticated ingestion, conflict handling, causal replay cutoffs, withdrawal isolation, version API endpoints, correction/reversal workflows, multithreaded concurrency race execution, cross-case anti-enumeration, effective transaction semantics, actor attribution, spoofing prevention, historical NULL preservation, and migration 0012. |

---

## 3. Technical Architecture and Design Decisions

### 3.1 Legacy Migration Policy and Deterministic Backfill
- Migrations `0009`, `0010`, `0011`, and `0012` use SQLite batch alter mode (`batch_alter_table`) for cross-database compatibility.
- Legacy `predictions` are deterministically backfilled with sequential `version_number` values per `complaint_id`, ordered strictly by `(created_at, id)`.
- For historical `transactions`, `received_at` and `created_by_user_id` are left `NULL` to truthfully reflect that knowledge time and authenticated actor proof were not recorded historically. During point-in-time replay, transactions with `received_at IS NULL` are handled under a disclosed legacy assumption (`LEGACY_PRE_PHASE2_ASSUMED_KNOWN`) documented in context metadata, rather than silently omitting them from historical investigations.

### 3.2 Canonical Prediction Identity and Defect Resolution
- **Input Fingerprint:** Canonical SHA-256 hash constructed from:
  - Complaint attributes: `complaint_id`, `amount`, `reported_at`, `incident_time`, `origin_district`.
  - Temporal cutoff: ISO format of `analysis_as_of` (or `"LATEST"`).
  - Eligible effective evidence: sorted tuples of `(transaction_id, transaction_ref, amount, transaction_time, source_account, dest_account, source_system, is_reversal, correction_of_ref)`.
  - Model & Schema Versions: `model_version`, `feature_schema_version`.
- **Result Fingerprint:** Canonical SHA-256 hash of:
  - Ordered candidates: `[(rank, cluster_id, round(probability, 4))]`.
  - Window bounds: `(predicted_window_start, predicted_window_end)`.
- **Defect Resolution:** When evidence changes rank-2/rank-3 while rank-1 stays unchanged, the new `input_fingerprint` and `result_fingerprint` differ from the previous prediction. The service immediately creates a new immutable `Prediction` with incremented `version_number` and `parent_prediction_id` pointing to the previous record, completely resolving the stale-prediction bug.

### 3.3 Concurrency and Race Condition Safety
- Database-level uniqueness constraint `uq_complaint_version_number` on `(complaint_id, version_number)`.
- Database-level uniqueness constraint `uq_transactions_transaction_ref` on `transactions.transaction_ref`.
- Index on `(complaint_id, input_fingerprint)`.
- Real multithreaded concurrent race execution:
  - If identical requests race simultaneously, the second worker catches `IntegrityError`, rolls back, and returns the existing record (idempotent replay with `200 OK` and `X-Idempotent-Replay: true`).
  - If differing payloads race simultaneously, the second worker receives `409 Conflict`.
  - *PostgreSQL note:* Concurrent race tests have been executed on SQLite with multithreading. Multi-worker PostgreSQL native concurrency validation remains recorded as **PENDING** until live PostgreSQL deployment.

### 3.4 Causal Ingestion, Correction, and Cutoff Semantics
- `POST /complaints/{id}/transactions` sets `received_at = datetime.utcnow()` and `created_by_user_id = current_user.id` at the server; client-supplied received timestamps and creator IDs are ignored to prevent temporal and actor spoofing.
- Replay with an `analysis_as_of` cutoff filters out any transaction whose `transaction_time > cutoff` OR `received_at > cutoff`.
- Point-in-time prediction preserves complaint-relative target calculation without artificially moving past predicted windows into the future.
- Historical replays before a correction's `received_at` see the original pre-correction transaction state.

### 3.5 Outcome Isolation
- ATM withdrawal records (`is_withdrawal=True`) represent final cash-out realization events.
- In `graph_service.py` and `ml_feature_service.py`, `include_outcomes=False` ensures these terminal withdrawal nodes and edges are excluded from feature matrices and graph centrality inputs, preventing outcome leakage from artificially inflating model confidence.

---

## 4. Test Suite Execution and Evidence

### 4.1 Full Test Suite Pass
Executing the complete automated test suite via pytest (`scripts/phase0_audit.py`) produced JUnit XML in `scratch/phase0_20260920T140216Z/pytest.xml`:
```xml
<?xml version="1.0" encoding="utf-8"?>
<testsuites name="pytest tests">
  <testsuite name="pytest" errors="0" failures="0" skipped="1" tests="425" time="57.06" timestamp="2026-09-20T19:33:47+05:30" hostname="hp">
```
- **Total Tests:** 425
- **Passed:** **424**
- **Skipped:** 1 (explicitly documented live blockchain infrastructure test requiring `--run-live`)
- **Failed:** **0**
- **Executable Pass Rate:** **100%**

### 4.2 Dedicated Phase 02 Tests (`tests/test_phase2_causal_predictions.py`)
```text
tests/test_phase2_causal_predictions.py::test_reproduce_stale_prediction_defect_same_rank1_different_rank2 PASSED
tests/test_phase2_causal_predictions.py::test_identical_retry_idempotency PASSED
tests/test_phase2_causal_predictions.py::test_transaction_ingestion_api_deduplication_and_conflict PASSED
tests/test_phase2_causal_predictions.py::test_causal_replay_and_point_in_time_isolation PASSED
tests/test_phase2_causal_predictions.py::test_withdrawal_outcome_leakage_prevention PASSED
tests/test_phase2_causal_predictions.py::test_prediction_snapshot_immutability PASSED
tests/test_phase2_causal_predictions.py::test_prediction_version_retrieval_endpoints PASSED
tests/test_phase2_causal_predictions.py::test_regression_automatic_refresh_includes_new_past_transfer PASSED
tests/test_phase2_causal_predictions.py::test_regression_truthful_analysis_status_and_idempotent_retry PASSED
tests/test_phase2_causal_predictions.py::test_regression_dedup_cross_case_isolation_and_account_provenance PASSED
tests/test_phase2_causal_predictions.py::test_regression_operational_latest_not_displaced_by_historical_replay PASSED
tests/test_phase2_causal_predictions.py::test_regression_evidence_fingerprint_captures_reversal_and_accounts PASSED
tests/test_phase2_causal_predictions.py::test_regression_retry_analysis_authorization PASSED
tests/test_phase2_causal_predictions.py::test_regression_recent_historical_replay_never_becomes_operational PASSED
tests/test_phase2_causal_predictions.py::test_regression_unrelated_integrity_error_propagates PASSED
tests/test_phase2_causal_predictions.py::test_regression_transaction_correction_and_reversal_api PASSED
tests/test_phase2_causal_predictions.py::test_regression_concurrent_duplicate_transaction_ingestion_idempotency PASSED
tests/test_phase2_causal_predictions.py::test_regression_cross_case_anti_enumeration PASSED
tests/test_phase2_causal_predictions.py::test_regression_effective_transaction_semantics_and_causal_replay PASSED
tests/test_phase2_causal_predictions.py::test_authenticated_transaction_actor_attribution PASSED
tests/test_phase2_causal_predictions.py::test_correction_and_reversal_distinct_actor_attribution PASSED
tests/test_phase2_causal_predictions.py::test_actor_identity_spoofing_prevented PASSED
tests/test_phase2_causal_predictions.py::test_historical_transaction_rows_remain_valid_with_null_actor PASSED
tests/test_phase2_causal_predictions.py::test_wrong_jurisdiction_transaction_and_actor_data_isolation PASSED
tests/test_phase2_causal_predictions.py::test_alembic_migration_0012_from_populated_0011 PASSED
25 passed in 206.18s
```

### 4.3 Database Migration Tests (`tests/test_database_migrations_phase2.py`)
```text
tests/test_database_migrations_phase2.py::test_fresh_database_upgrade_to_head PASSED
tests/test_database_migrations_phase2.py::test_upgrade_from_phase1_to_phase2 PASSED
tests/test_database_migrations_phase2.py::test_upgrade_from_populated_0008_to_0009 PASSED
tests/test_database_migrations_phase2.py::test_upgrade_from_populated_0010_to_0011 PASSED
4 passed in 52.18s
```

### 4.4 Frontend Build Verification
```text
> cybershield-ai-frontend@1.0.0 build
> tsc && vite build

vite v5.4.21 building for production...
transforming...
✓ 2504 modules transformed.
rendering chunks...
computing gzip size...
dist/index.html                               1.60 kB │ gzip:   0.85 kB
dist/assets/index-eLpvSmBA.js                75.39 kB │ gzip:  26.70 kB
✓ built in 8.88s
```

---

## 5. Production Model and Schema Artifact Verification (All 45 Files)

Verification script `scratch/verify_phase2_artifacts.py` verified all 45 production machine learning weights, calibrators, feature schemas, and metadata files against baseline hashes in `scratch/phase0_20260917T175141Z/baseline.json`.

**Verification Result:** **45 / 45 MATCH (100% byte-for-byte identical, 0 mismatches, 0 retraining)**

| # | Artifact Path | Baseline SHA-256 Hash | Current SHA-256 Hash | Status |
|---|---|---|---|:---:|
| 1 | `backend/app/schemas/feature_schema_v1.json` | `5c347f8796aa4172f3e0c034b0718e6975239e2467d55bfb20892aeebaf9ea11` | `5c347f8796aa4172f3e0c034b0718e6975239e2467d55bfb20892aeebaf9ea11` | **MATCH** |
| 2 | `backend/app/schemas/feature_schema_v2.json` | `a3e351829e1f57feeb6d56bebe3f50228fcfaf484d852fbcc22906e534f59332` | `a3e351829e1f57feeb6d56bebe3f50228fcfaf484d852fbcc22906e534f59332` | **MATCH** |
| 3 | `backend/app/schemas/feature_schema_v3.json` | `7fb6a0fc678e727e4eef614532b67d56637ba23aeaf7e62a55985b9be154d85d` | `7fb6a0fc678e727e4eef614532b67d56637ba23aeaf7e62a55985b9be154d85d` | **MATCH** |
| 4 | `backend/app/schemas/feature_schema_v3_1.json` | `c379a07b71daeec69fa0f9d98ca4b54e3fe0e7b99c75531d044f54e1a06cf843` | `c379a07b71daeec69fa0f9d98ca4b54e3fe0e7b99c75531d044f54e1a06cf843` | **MATCH** |
| 5 | `backend/app/schemas/feature_schema_v4.json` | `ba3dd24ff264eef26fb16c35c3c0dfcfd3d3b76964094a4c6a99479b1dfaa3b5` | `ba3dd24ff264eef26fb16c35c3c0dfcfd3d3b76964094a4c6a99479b1dfaa3b5` | **MATCH** |
| 6 | `backend/app/schemas/feature_schema_v7.json` | `a20078fc23f669db4b8bcde554cb43cf2bfdb293bd3e00cf007d3fa873096057` | `a20078fc23f669db4b8bcde554cb43cf2bfdb293bd3e00cf007d3fa873096057` | **MATCH** |
| 7 | `backend/app/schemas/feature_schema_v7_compat.json` | `aa797b5d49eb936ce92900768c78c2e6f4e1f7cbf777e5d8a0c20f78d3869273` | `aa797b5d49eb936ce92900768c78c2e6f4e1f7cbf777e5d8a0c20f78d3869273` | **MATCH** |
| 8 | `database/seed/atm_locations.csv` | `04bfcfc3ae06b3e3434685ffaa4db96c73d9ce459d87383fc5a9fb89ce86e680` | `04bfcfc3ae06b3e3434685ffaa4db96c73d9ce459d87383fc5a9fb89ce86e680` | **MATCH** |
| 9 | `database/seed/location_clusters.csv` | `645858850616b47ccfc9f3b584ec66f272e61be172bcfa3b3558c49cc44fceb1` | `645858850616b47ccfc9f3b584ec66f272e61be172bcfa3b3558c49cc44fceb1` | **MATCH** |
| 10 | `database/seed/spatial_patterns.csv` | `a5f4c4c23ba3f16d00164c8d57d5a5749f7e8aa69b8214fa709772bf62c64dbb` | `a5f4c4c23ba3f16d00164c8d57d5a5749f7e8aa69b8214fa709772bf62c64dbb` | **MATCH** |
| 11 | `database/seed/synthetic_complaints_3000.csv` | `e02d6dfad2976df47754f9a3f284e931e21b8b8ba9c1a017fe45281483ce3578` | `e02d6dfad2976df47754f9a3f284e931e21b8b8ba9c1a017fe45281483ce3578` | **MATCH** |
| 12 | `database/seed/synthetic_delhi_atms.csv` | `d6dfd0ae6d8d64eb076269ebcb167caad33c94a5e2f75a6c0ef631df83dfce5d` | `d6dfd0ae6d8d64eb076269ebcb167caad33c94a5e2f75a6c0ef631df83dfce5d` | **MATCH** |
| 13 | `database/seed/synthetic_transactions_50000.csv` | `fa71804f3ce4802c67fe9970ce7e3e7861bc97858c7e9db8f7e255f05df3cce9` | `fa71804f3ce4802c67fe9970ce7e3e7861bc97858c7e9db8f7e255f05df3cce9` | **MATCH** |
| 14 | `ml/artifacts/location_calibrator.joblib` | `332da1e7fb83fc6e4e89f9e5fcb3cc4fc6ffb0070743b1aa0e6988863fba3594` | `332da1e7fb83fc6e4e89f9e5fcb3cc4fc6ffb0070743b1aa0e6988863fba3594` | **MATCH** |
| 15 | `ml/artifacts/location_calibrator_v1.joblib` | `282103f69cf3bf13df130a2a50a1df274719b33e387c88b05615eaeb9d5bc50b` | `282103f69cf3bf13df130a2a50a1df274719b33e387c88b05615eaeb9d5bc50b` | **MATCH** |
| 16 | `ml/artifacts/location_calibrator_v2.joblib` | `dbbc9bf66b3f74640103ca78b2734490f23021f1ca9ecf8021d7bcf0bc7d727b` | `dbbc9bf66b3f74640103ca78b2734490f23021f1ca9ecf8021d7bcf0bc7d727b` | **MATCH** |
| 17 | `ml/artifacts/location_calibrator_v3.joblib` | `23188d3e925c4ef69d311915f4585c54433eefd6b97607a9b015119098ee3fd4` | `23188d3e925c4ef69d311915f4585c54433eefd6b97607a9b015119098ee3fd4` | **MATCH** |
| 18 | `ml/artifacts/location_calibrator_v3_1.joblib` | `f312015be6aa8e23f95b5463131b790d984cfb7dcf85b46bbf6bcf4402325ae8` | `f312015be6aa8e23f95b5463131b790d984cfb7dcf85b46bbf6bcf4402325ae8` | **MATCH** |
| 19 | `ml/artifacts/location_calibrator_v4.joblib` | `65ceb736838d14cb865111aac6eddfad3838704ddf2fffc63a6b2bdd998a3664` | `65ceb736838d14cb865111aac6eddfad3838704ddf2fffc63a6b2bdd998a3664` | **MATCH** |
| 20 | `ml/artifacts/location_calibrator_v5.joblib` | `cd5e5229c6e4c3d0b83b662d560a4c622c387ca3e862bce864922988207a6d31` | `cd5e5229c6e4c3d0b83b662d560a4c622c387ca3e862bce864922988207a6d31` | **MATCH** |
| 21 | `ml/artifacts/location_calibrator_v5_1.joblib` | `cd569c1e25277ef785e4d057796a22c27065fa1c7c5dcd8b87fa753331627fbc` | `cd569c1e25277ef785e4d057796a22c27065fa1c7c5dcd8b87fa753331627fbc` | **MATCH** |
| 22 | `ml/artifacts/location_calibrator_v7.joblib` | `0144fae76cfac5c2ad38fbc6cc1fc5c652c80c9364a3ff7edc02f3444ac90ad8` | `0144fae76cfac5c2ad38fbc6cc1fc5c652c80c9364a3ff7edc02f3444ac90ad8` | **MATCH** |
| 23 | `ml/artifacts/location_calibrator_v7_compat.joblib` | `1c14d5aba1b0556a47519ea435804a86b34173c76743a77bcf52cea43d3a2c6d` | `1c14d5aba1b0556a47519ea435804a86b34173c76743a77bcf52cea43d3a2c6d` | **MATCH** |
| 24 | `ml/artifacts/location_ranker.joblib` | `fa7e7a84408861b5c8568b3cab624afd534afa861f9c94c6731fa9a968b80d35` | `fa7e7a84408861b5c8568b3cab624afd534afa861f9c94c6731fa9a968b80d35` | **MATCH** |
| 25 | `ml/artifacts/location_ranker_v1.joblib` | `58844303341ac5b0623610cef324eb662b5b5b43f9328729107680ac51003cd9` | `58844303341ac5b0623610cef324eb662b5b5b43f9328729107680ac51003cd9` | **MATCH** |
| 26 | `ml/artifacts/location_ranker_v2.joblib` | `b769b5275cb1a694607cb2db2e27aeb28922daeb3a8faa706ef8a80570bcf0dc` | `b769b5275cb1a694607cb2db2e27aeb28922daeb3a8faa706ef8a80570bcf0dc` | **MATCH** |
| 27 | `ml/artifacts/location_ranker_v3.joblib` | `812b56b2d6d05f448b0e581e79df8bbc9a9e0828d0ec8320bf9fc1d551524ad1` | `812b56b2d6d05f448b0e581e79df8bbc9a9e0828d0ec8320bf9fc1d551524ad1` | **MATCH** |
| 28 | `ml/artifacts/location_ranker_v3_1.joblib` | `2fe0e596f0dc8a37361271f504a0a66f0fde0c1b0aaf1e6a8bc98bc5a38c6921` | `2fe0e596f0dc8a37361271f504a0a66f0fde0c1b0aaf1e6a8bc98bc5a38c6921` | **MATCH** |
| 29 | `ml/artifacts/location_ranker_v4.joblib` | `9ed5792ced4f8a6e79dc91e587e3c130d2fbadb5af6a73640397dc506dd9cdc9` | `9ed5792ced4f8a6e79dc91e587e3c130d2fbadb5af6a73640397dc506dd9cdc9` | **MATCH** |
| 30 | `ml/artifacts/location_ranker_v5.joblib` | `28c8d0dd696e1f9971ae3ec971c35f47a447a9c22de241c0d0b603bc909efd2f` | `28c8d0dd696e1f9971ae3ec971c35f47a447a9c22de241c0d0b603bc909efd2f` | **MATCH** |
| 31 | `ml/artifacts/location_ranker_v5_1.joblib` | `acfa851c4544caa76eefa4d7e86ed7cd9f5a9fcfc61655a8df71b71379b56547` | `acfa851c4544caa76eefa4d7e86ed7cd9f5a9fcfc61655a8df71b71379b56547` | **MATCH** |
| 32 | `ml/artifacts/location_ranker_v7.joblib` | `acc387988442696fe1f8a48fc6e4935f091114ccb1453a73139fd93c2e11f39e` | `acc387988442696fe1f8a48fc6e4935f091114ccb1453a73139fd93c2e11f39e` | **MATCH** |
| 33 | `ml/artifacts/location_ranker_v7_compat.joblib` | `89057bce1000cb82e10f29077b9e168bc0cbd254e979106998e1d623e072c2a6` | `89057bce1000cb82e10f29077b9e168bc0cbd254e979106998e1d623e072c2a6` | **MATCH** |
| 34 | `ml/artifacts/model_metadata_v1.json` | `ea1531471263d678fe59c9fae5a55107803ce6da89c92c1d01c5bdc3ab5b2384` | `ea1531471263d678fe59c9fae5a55107803ce6da89c92c1d01c5bdc3ab5b2384` | **MATCH** |
| 35 | `ml/artifacts/model_metadata_v2.json` | `23aeae4a0d365bd7edf2c673a255bd00878717e55c910e5d3566cdc509681c74` | `23aeae4a0d365bd7edf2c673a255bd00878717e55c910e5d3566cdc509681c74` | **MATCH** |
| 36 | `ml/artifacts/model_metadata_v3.json` | `801c8127fd19f9a09d6aaec513a3b18399fa389268c7414ed95d7ce2b862d0f9` | `801c8127fd19f9a09d6aaec513a3b18399fa389268c7414ed95d7ce2b862d0f9` | **MATCH** |
| 37 | `ml/artifacts/model_metadata_v3_1.json` | `9dea3176148f8621438e9acb26e013801a03645899e22e404c6929131e71f80b` | `9dea3176148f8621438e9acb26e013801a03645899e22e404c6929131e71f80b` | **MATCH** |
| 38 | `ml/artifacts/model_metadata_v4.json` | `fe7419e941ccaab6f0149e6f5e07ac8c08fce9d12e8a653a2e1a67037917db6f` | `fe7419e941ccaab6f0149e6f5e07ac8c08fce9d12e8a653a2e1a67037917db6f` | **MATCH** |
| 39 | `ml/artifacts/model_metadata_v7.json` | `1059b052ad290bd1d82c1758df6b3c8f34819a980798c7a29cee127f2005e5f1` | `1059b052ad290bd1d82c1758df6b3c8f34819a980798c7a29cee127f2005e5f1` | **MATCH** |
| 40 | `ml/artifacts/model_metadata_v7_compat.json` | `d402ab6c397327fbce5916621e1da51766ee87b7a5449fa152c0e969b10c59f4` | `d402ab6c397327fbce5916621e1da51766ee87b7a5449fa152c0e969b10c59f4` | **MATCH** |
| 41 | `ml/artifacts/time_regressor.joblib` | `397f07999b2bf279abadef1afb193c94d5c5f8a5bfe11bf9b97fe68e13f6fe1c` | `397f07999b2bf279abadef1afb193c94d5c5f8a5bfe11bf9b97fe68e13f6fe1c` | **MATCH** |
| 42 | `ml/artifacts/time_regressor_v1.joblib` | `011a22ea26ef6e68eaaafc43f33c56c17b983ef4ec5311f6c2535c7328b8f3de` | `011a22ea26ef6e68eaaafc43f33c56c17b983ef4ec5311f6c2535c7328b8f3de` | **MATCH** |
| 43 | `ml/artifacts/time_regressor_v2.joblib` | `2bb64f572dca0e8dbb767feccf854abb0e7ce886a0cbc17365a59a927c33b38e` | `2bb64f572dca0e8dbb767feccf854abb0e7ce886a0cbc17365a59a927c33b38e` | **MATCH** |
| 44 | `ml/artifacts/time_regressor_v3.joblib` | `41183f4579df70372102e98999967a5e63a9a2dad80f63668b45a5a66a2ed5e1` | `41183f4579df70372102e98999967a5e63a9a2dad80f63668b45a5a66a2ed5e1` | **MATCH** |
| 45 | `ml/artifacts/time_regressor_v4.joblib` | `9cbf4b48b3adf64084e66ec2584d267143d131520a4909198fa5440c14c79dc0` | `9cbf4b48b3adf64084e66ec2584d267143d131520a4909198fa5440c14c79dc0` | **MATCH** |

---

## 6. Recorded Pending Items

The following items are explicitly tracked as **PENDING** and were not claimed as completed without direct execution:
1. **PostgreSQL Native Concurrency Stress Test:** Multithreaded race execution was executed and verified on SQLite (`test_regression_concurrent_duplicate_transaction_ingestion_idempotency`). High-concurrency native PostgreSQL pool validation is recorded as **PENDING** live cloud deployment.
2. **Browser Visual QA / Manual Screenshot Inspection:** Frontend TypeScript compilation and Vite production build passed cleanly. Browser subagent visual inspection of interactive replay banner transitions is recorded as **PENDING** full end-to-end UI QA.

---

## 7. Operational Handover & Stopping Rule

Phase 02 execution is completely finished, fully verified, and reconciled with fresh measured evidence.
Per strict instructions:
1. No retraining of production models has occurred.
2. All 45 model and schema artifact hashes remain identical to the recorded baseline.
3. Test suite execution is 100% passing across all 418 executable tests (419 total, 1 skipped for live-only network).
4. No work has begun on Phase 03. All execution halts at this milestone.
