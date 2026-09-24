# CyberShield AI — Repository Public Upload Manifest

**Date:** 21 September 2026  
**Purpose:** Comprehensive audit and classification of repository paths for safe public GitHub source code repository upload.  
**Classification Rules:**
- `SOURCE_TO_INCLUDE`: Production application source code, API routes, database models, schemas, services, utilities, UI components, Docker configurations, and configuration templates.
- `DOCUMENTATION_TO_INCLUDE`: Architecture documentation, phase implementation handoffs, operational runbooks, problem statement matrices, audit logs, and onboarding guides.
- `TEST_TO_INCLUDE`: Pytest test suites, fixtures, end-to-end integration tests, and verification test harnesses.
- `GENERATED_RUNTIME_DO_NOT_UPLOAD`: Ephemeral artifacts, test execution outputs, compiled bundles, build caches, temporary test outputs.
- `PRIVATE_CONFIG_DO_NOT_UPLOAD`: Local secrets, active environment variable files (`.env`), credentials, API keys.
- `LOCAL_DATA_DO_NOT_UPLOAD`: Local SQLite databases, binary test evidence files, storage uploads, research data archives, temporary scratch files.

---

## 1. Classification Summary Table

| Category | Classification Tag | Description | Action for Git Upload |
|---|---|---|---|
| **Backend Core & Services** | `SOURCE_TO_INCLUDE` | FastAPI application, routes, models, schemas, auth, outbox, and services | **INCLUDE** |
| **Alembic Migrations** | `SOURCE_TO_INCLUDE` | Linear migration sequence (0001 through 0019) and env configuration | **INCLUDE** |
| **Frontend Application** | `SOURCE_TO_INCLUDE` | React, TypeScript, Leaflet/Map components, pages, utils, types, styling | **INCLUDE** |
| **Machine Learning Core** | `SOURCE_TO_INCLUDE` | Feature pipelines, candidate generators, evaluation engines, promotion gates | **INCLUDE** |
| **Promoted ML Artifacts** | `SOURCE_TO_INCLUDE` | 31 tracked files in `ml/artifacts/`, including the active V8 model and metadata. The older 45-file local baseline includes 21 ignored historical model files that are not uploaded. | **INCLUDE TRACKED FILES** |
| **Configuration Templates** | `SOURCE_TO_INCLUDE` | `.env.example`, `docker-compose.yml`, `pytest.ini`, `package.json`, `tsconfig.json` | **INCLUDE** |
| **Documentation & Runbooks** | `DOCUMENTATION_TO_INCLUDE` | Implementation handoffs (Phases 00–13), PS Traceability, Runbooks, Manifests | **INCLUDE** |
| **Test Suites & Fixtures** | `TEST_TO_INCLUDE` | Complete unit, integration, and regression test suites across all phases | **INCLUDE** |
| **Local Environment Files** | `PRIVATE_CONFIG_DO_NOT_UPLOAD` | `.env`, `frontend/.env`, `frontend/.env.local`, `.env.*` | **EXCLUDE (Ignored)** |
| **Generated Test & Build Outputs** | `GENERATED_RUNTIME_DO_NOT_UPLOAD` | `reports/`, `frontend/dist/`, `__pycache__/`, `.pytest_cache/`, `tmp/` | **EXCLUDE (Ignored)** |
| **Local Storage & Evidence** | `LOCAL_DATA_DO_NOT_UPLOAD` | `backend/storage/`, `scratch/`, `*.sqlite3`, `*.db`, `ml/data/*.csv.gz` | **EXCLUDE (Ignored)** |
| **Virtual Environments & Deps** | `GENERATED_RUNTIME_DO_NOT_UPLOAD` | `.venv/`, `node_modules/`, `venv/` | **EXCLUDE (Ignored)** |

---

## 2. Exhaustive Path-by-Path Manifest

### A. Source Code (`SOURCE_TO_INCLUDE`)

#### Backend & API Layer
- `backend/app/__init__.py`
- `backend/app/main.py`
- `backend/app/config/__init__.py`
- `backend/app/config/settings.py`
- `backend/app/auth/__init__.py`
- `backend/app/auth/rbac.py`
- `backend/app/auth/security.py`
- `backend/app/models/__init__.py`
- `backend/app/models/db.py`
- `backend/app/models/models.py`
- `backend/app/schemas/__init__.py`
- `backend/app/schemas/schemas.py`
- `backend/app/api/__init__.py`
- `backend/app/api/alert_routes.py`
- `backend/app/api/analytics_routes.py`
- `backend/app/api/audit_routes.py`
- `backend/app/api/auth_routes.py`
- `backend/app/api/bank_action_routes.py`
- `backend/app/api/complaint_routes.py`
- `backend/app/api/evidence_routes.py`
- `backend/app/api/geography_routes.py`
- `backend/app/api/gis_routes.py`
- `backend/app/api/handoff_routes.py`
- `backend/app/api/model_routes.py`
- `backend/app/api/outcome_routes.py`
- `backend/app/api/prediction_routes.py`
- `backend/app/api/report_routes.py`
- `backend/app/api/system_routes.py`
- `backend/app/api/transaction_routes.py`
- `backend/app/adapters/__init__.py`
- `backend/app/adapters/bank_adapter.py`
- `backend/app/services/__init__.py`
- `backend/app/services/alert_service.py`
- `backend/app/services/audit_service.py`
- `backend/app/services/bank_action_service.py`
- `backend/app/services/dashboard_service.py`
- `backend/app/services/evidence_service.py`
- `backend/app/services/geography_catalog_service.py`
- `backend/app/services/graph_service.py`
- `backend/app/services/handoff_service.py`
- `backend/app/services/ml_feature_service.py`
- `backend/app/services/model_verification_service.py`
- `backend/app/services/outbox_service.py`
- `backend/app/services/outcome_service.py`
- `backend/app/services/prediction_audit_service.py`
- `backend/app/services/prediction_contract.py`
- `backend/app/services/prediction_explainability_service.py`
- `backend/app/services/prediction_persistence_service.py`
- `backend/app/services/prediction_service.py`
- `backend/app/services/report_service.py`
- `backend/app/services/transaction_context_service.py`
- `backend/app/websocket/__init__.py`
- `backend/app/websocket/manager.py`
- `backend/Dockerfile`
- `backend/requirements.txt`

#### Alembic Database Migrations
- `alembic.ini`
- `alembic/env.py`
- `alembic/script.py.mako`
- `alembic/versions/0001_initial_baseline.py`
- `alembic/versions/0002_add_auth_and_rbac.py`
- `alembic/versions/0003_add_gis_and_spatial.py`
- `alembic/versions/0004_add_audit_and_evidence.py`
- `alembic/versions/0005_add_prediction_provenance.py`
- `alembic/versions/0006_add_graph_and_mule_nodes.py`
- `alembic/versions/0007_add_bank_actions.py`
- `alembic/versions/0008_add_reports_and_dossiers.py`
- `alembic/versions/0009_phase2_causal_transactions_and_versioning.py`
- `alembic/versions/0010_explicit_analysis_purpose.py`
- `alembic/versions/0011_canonical_transaction_dedup.py`
- `alembic/versions/0012_transaction_created_by_user_id.py`
- `alembic/versions/0013_phase3_authorization_scope_ids.py`
- `alembic/versions/0014_phase5_durable_alerts_and_outbox.py`
- `alembic/versions/0015_phase6_evidence_and_reports.py`
- `alembic/versions/0016_phase7_cross_state_handoff.py`
- `alembic/versions/0017_phase8_bank_adapter_and_lifecycle.py`
- `alembic/versions/0018_phase9_outcome_observations.py`
- `alembic/versions/0019_phase12_geography_catalog_and_regions.py`

#### Machine Learning & Evaluation Engine
- `ml/features/__init__.py`
- `ml/features/feature_pipeline.py`
- `ml/geo/__init__.py`
- `ml/geo/candidate_generator.py`
- `ml/evaluation/__init__.py`
- `ml/evaluation/dataset_inventory.py`
- `ml/evaluation/lime_stability_evaluation.py`
- `ml/evaluation/promotion_gates.py`
- `ml/evaluation/real_data_validator.py`
- `ml/evaluation/reproducible_evaluator.py`
- `ml/evaluation/second_region_readiness.py`
- `ml/evaluation/timing_evaluation.py`
- `ml/artifacts/.gitkeep`
- `ml/artifacts/location_ranker_v4.joblib`
- `ml/artifacts/location_calibrator_v4.joblib`
- `ml/artifacts/location_ranker_v7_compat.joblib`
- `ml/artifacts/location_calibrator_v7_compat.joblib`
- `ml/artifacts/time_regressor_v3.joblib`
- `ml/artifacts/*.json` (40 metadata & evaluation manifests strictly preserved)

#### Database Seed & Scripts
- `database/seed/seed_data.py`
- `database/seed/synthetic_generator.py`
- `scripts/generate_antigravity_plan.py`
- `scripts/phase0_audit.py`
- `scripts/phase0_case_probe.py`
- `scripts/phase0_database_snapshot.py`
- `scripts/phase0_report.py`

#### Frontend User Interface
- `frontend/package.json`
- `frontend/package-lock.json`
- `frontend/tsconfig.json`
- `frontend/tsconfig.node.json`
- `frontend/vite.config.ts`
- `frontend/tailwind.config.js`
- `frontend/postcss.config.js`
- `frontend/index.html`
- `frontend/Dockerfile`
- `frontend/src/App.tsx`
- `frontend/src/main.tsx`
- `frontend/src/index.css`
- `frontend/src/types/index.ts`
- `frontend/src/services/api.ts`
- `frontend/src/utils/predictionDisplay.ts`
- `frontend/src/components/*` (all UI components)
- `frontend/src/maps/*` (Leaflet & Google Maps style engines)
- `frontend/src/pages/*` (all dashboards, analytics, alerts, reports, cases, outcomes)

#### Repository Configuration & Deployment
- `.gitignore`
- `.env.example`
- `docker-compose.yml`
- `pytest.ini`

---

### B. Documentation (`DOCUMENTATION_TO_INCLUDE`)
- `README.md`
- `docs/remediation-plan.md`
- `docs/phase0/AUDIT_REPORT.md`
- `docs/phase0/PS_TRACEABILITY.md`
- `docs/phase0/DATABASE_VERIFICATION.md`
- `docs/antigravity/*.md` (all 14 phase instruction guides)
- `docs/antigravity/manifest.json`
- `docs/implementation/PHASE_00_RESULT.md` through `PHASE_13_RESULT.md`
- `docs/implementation/FINAL_PS_ACCEPTANCE_MATRIX.md`
- `docs/implementation/PILOT_READINESS_CHECKLIST.md`
- `docs/implementation/OPERATIONAL_RUNBOOK.md`
- `docs/implementation/UPLOAD_MANIFEST.md`
- `docs/implementation/UPLOAD_READINESS_RESULT.md`

---

### C. Test Suites (`TEST_TO_INCLUDE`)
- `tests/conftest.py`
- `tests/test_backend.py`
- `tests/test_blockchain_feature_parity.py`
- `tests/test_blockchain_signal_causality_audit.py`
- `tests/test_code_consolidation.py`
- `tests/test_complaint_intake_e2e.py`
- `tests/test_complaint_scenario_linking.py`
- `tests/test_cors_configuration.py`
- `tests/test_database_migrations_phase2.py`
- `tests/test_delhi_intake_map_regression.py`
- `tests/test_dynamic_transaction_graph.py`
- `tests/test_environment_profiles.py`
- `tests/test_final_e2e_fresh_complaint.py`
- `tests/test_ml_pipeline.py`
- `tests/test_ml_quality_improvements.py`
- `tests/test_ml_remediation.py`
- `tests/test_model_verification.py`
- `tests/test_phase1_security_authorization.py`
- `tests/test_phase2_causal_predictions.py`
- `tests/test_phase2_timestamp_and_scores.py`
- `tests/test_phase3_authorization_matrix.py`
- `tests/test_phase3_hotspots_and_gis.py`
- `tests/test_phase4_gis_filters.py`
- `tests/test_phase4_model_performance.py`
- `tests/test_phase5_durable_alerts.py`
- `tests/test_phase5_lime_explainability.py`
- `tests/test_phase6_evidence_and_reports.py`
- `tests/test_phase6_graph_contracts.py`
- `tests/test_phase7_cross_state_handoff.py`
- `tests/test_phase8_bank_adapter.py`
- `tests/test_phase9_outcome_observations.py`
- `tests/test_phase10_model_evaluation.py`
- `tests/test_phase11_timing_and_lime.py`
- `tests/test_phase12_geography_and_regions.py`
- `tests/test_phase13_integrated_workflow.py`
- `tests/test_phase13_load_benchmarks.py`
- `tests/test_phase13_unhappy_and_recovery.py`
- `tests/test_prediction_explainability_lime.py`
- `tests/test_prediction_idempotency.py`
- `tests/test_prediction_time_metadata_regression.py`
- `tests/test_schema_hardening.py`
- `tests/test_step9_prediction_flow.py`
- `tests/test_step10_prediction_persistence.py`
- `tests/test_step11_gis_persistence_integration.py`
- `tests/test_step12_prediction_alert_integration.py`
- `tests/test_step13_dashboard_db_integration.py`
- `tests/test_step14_auth_audit.py`
- `tests/test_synthetic_seed.py`
- `tests/test_system_status.py`
- `tests/test_transaction_scenario_linking.py`
- `tests/test_v7_compat_runtime_parity.py`
- `tests/test_websocket_reliability.py`

---

## 3. Explicitly Excluded Paths (`DO_NOT_UPLOAD`)

| Path / Pattern | Classification | Exclusion Justification |
|---|---|---|
| `.env`, `.env.local`, `.env.*` | `PRIVATE_CONFIG_DO_NOT_UPLOAD` | Local runtime configurations; must never be committed to source control. |
| `frontend/.env`, `frontend/.env.local` | `PRIVATE_CONFIG_DO_NOT_UPLOAD` | Local frontend environment overrides. |
| `backend/storage/` | `LOCAL_DATA_DO_NOT_UPLOAD` | Local filesystem storage for evidence attachments, signed dossier PDFs. |
| `reports/` | `GENERATED_RUNTIME_DO_NOT_UPLOAD` | Local pytest test execution reports, XML coverage outputs. |
| `tmp/`, `scratch/` | `GENERATED_RUNTIME_DO_NOT_UPLOAD` | Temporary scratch scripts, ephemeral investigation logs. |
| `.venv/`, `venv/`, `env/` | `GENERATED_RUNTIME_DO_NOT_UPLOAD` | Python virtual environments and installed binary packages. |
| `node_modules/` | `GENERATED_RUNTIME_DO_NOT_UPLOAD` | Node.js dependency trees. |
| `frontend/dist/` | `GENERATED_RUNTIME_DO_NOT_UPLOAD` | Local production bundle build output. |
| `*.sqlite3`, `*.db`, `backend/*.db` | `LOCAL_DATA_DO_NOT_UPLOAD` | Local development and testing databases. |
| `ml/data/*.csv.gz`, `ml/data/*.pkl` | `LOCAL_DATA_DO_NOT_UPLOAD` | Large synthetic training dataset archives and intermediate binary dumps. |
| `ml/research_backup/` | `LOCAL_DATA_DO_NOT_UPLOAD` | Historical exploration checkpoints. |
| `blockchain/network/organizations/` | `LOCAL_DATA_DO_NOT_UPLOAD` | Local crypto material and channel block artifacts. |
| `__pycache__/`, `*.py[cod]` | `GENERATED_RUNTIME_DO_NOT_UPLOAD` | Python bytecode caches. |
| `.idea/`, `.vscode/` | `GENERATED_RUNTIME_DO_NOT_UPLOAD` | Local IDE editor configurations. |

---

## 4. Verification Checkpoint

- **Excluded files on disk:** 100% preserved locally; zero deletions.
- **Git Ignore Status:** All excluded paths are ignored by `.gitignore`.
- **Public Upload Status:** Verified clean.
