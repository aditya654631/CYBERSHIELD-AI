# Phase 00 Handoff: Baseline Protection and Measured Audit

**Phase Number:** 00  
**Phase Title:** Baseline Protection and Measured Audit  
**Dependencies:** None  
**Baseline Git Commit:** `90e792eba9f50e135367cf65c3a09658c61471df` (clean checkout of branch `main`)  
**Audit Reference Date:** 17 September 2026 UTC (reconciled and verified on 19 September 2026)  
**Problem Statement Traceability:** PS-01 through PS-25 (Evidence baseline established)  

---

## 1. Executive Summary

Phase 00 establishes the verified baseline of the CyberShield AI repository prior to any code modification, schema migration, or model retraining. In accordance with `START_HERE.md` and `PHASE_00.md`:
1. All working application code and model artifacts have been preserved without changes.
2. The measured audit evidence executed on 17 September 2026 UTC was inspected and verified against the unchanged application commit `90e792eba9f50e135367cf65c3a09658c61471df`.
3. Repository bundle and tracked worktree checkpoints were verified via separate directory restoration drills.
4. SQLite databases passed integrity checks (`PRAGMA integrity_check = ok`).
5. A consistent read-only data snapshot of configured PostgreSQL was captured (17 tables / 98,259 rows), while native `pg_dump` and isolated restore drill is recorded as **PENDING** due to local environment tool limitations.
6. The test failure baseline of 74 failures and 1 skip was classified into six distinct root causes.
7. All 25 Problem Statement clauses were mapped to actual repository evidence and concrete acceptance checks.
8. No application fixes, refactoring, or model retraining were performed in this phase.

---

## 2. Changed Files and Migrations

- **Application Code Changes:** None (`0` application source files modified).
- **Model Artifact Changes:** None (`0` models retrained; all 40 artifact SHA-256 hashes matched before and after).
- **Database Migrations:** None (`0` Alembic revisions created or run).
- **Files Added / Tracked for Audit & Phase Handoff:**
  - `docs/implementation/PHASE_00_RESULT.md` (this phase handoff document)
  - `docs/phase0/AUDIT_REPORT.md` (measured baseline report)
  - `docs/phase0/PS_TRACEABILITY.md` (25-row requirement traceability matrix)
  - `docs/phase0/TEST_FAILURES.csv` (itemized node IDs and failure messages for all 74 failures)
  - `docs/phase0/AUDIT_SUMMARY.json` (machine-readable execution summary)
  - `scripts/phase0_audit.py` (repeatable non-destructive audit automation)
  - `scripts/phase0_case_probe.py` (isolated synthetic complaint E2E probe)
  - `scripts/phase0_database_snapshot.py` (read-only PostgreSQL data extractor)
  - `scripts/phase0_report.py` (XML parser and failure aggregator)

---

## 3. Exact Test Commands, Runtimes, and Counts

All verification runs were executed against disposable, isolated environments with strict isolation flags (`ENVIRONMENT=test`, `DATABASE_URL=sqlite:///:memory:` or temporary bootstrap SQLite, `AUTO_SEED_DEMO_DATA=false`, `FABRIC_GATEWAY_URL=http://127.0.0.1:1/api/v1`).

| Test Suite / Command | Command Line | Working Directory | Exit Code | Runtime | Result Details |
|---|---|---|---|---|---|
| **Pytest Full Suite** | `.\.venv\Scripts\python.exe -m pytest tests -q -ra --junitxml=...` | Root | 1 | 132.72s | **321 passed, 74 failed, 1 skipped** (396 collected items; 37,173 warnings) |
| **Frontend TypeScript Typecheck** | `node frontend/node_modules/typescript/bin/tsc` | `frontend` | 0 | 8.42s | **0 errors, clean compile** |
| **Frontend Production Build** | `node frontend/node_modules/vite/bin/vite.js build --outDir ...` | `frontend` | 0 | 13.12s | **0 errors, production assets bundled** |
| **Fabric Gateway Unit Tests** | `node blockchain/gateway/node_modules/mocha/bin/mocha.js tests --recursive --timeout 20000` | `blockchain/gateway` | 0 | 22.44s | **21 passed, 0 failed** (mocked dependencies) |
| **Feature Engine Unit Tests** | `node blockchain/feature-engine/node_modules/mocha/bin/mocha.js tests --recursive --timeout 20000` | `blockchain/feature-engine` | 0 | 6.47s | **13 passed, 0 failed** |
| **Prediction Chaincode Tests** | `node blockchain/chaincode/prediction-audit/node_modules/mocha/bin/mocha.js test --recursive --timeout 20000` | `blockchain/chaincode/prediction-audit` | 0 | 11.03s | **10 passed, 0 failed** |
| **Geo Chaincode Tests** | `node blockchain/chaincode/geo-intelligence/node_modules/mocha/bin/mocha.js test --recursive --timeout 20000` | `blockchain/chaincode/geo-intelligence` | 0 | 7.31s | **17 passed, 0 failed** |
| **Total Blockchain Unit Tests** | *(Aggregated across 4 mocha suites)* | `blockchain/*` | 0 | 47.25s | **61 passed, 0 failed** |
| **Isolated GIS Module** | `pytest tests/test_phase3_hotspots_and_gis.py` | Root | 0 | ~12.0s | **14 passed, 0 failed** (5 failed only in full suite due to test state pollution) |
| **Fresh Complaint E2E Probe** | `.\.venv\Scripts\python.exe scripts/phase0_case_probe.py` | Root | 0 | ~18.5s | **Passed** (`demo_case_snapshot.json` saved; prediction, risk-map, graph, LIME status 200) |

---

## 4. Failure Classification (74 Failing Tests in Pytest)

The 74 failures captured in `docs/phase0/TEST_FAILURES.csv` and `docs/phase0/AUDIT_SUMMARY.json` do not represent 74 unique defects in application logic. They group into six clear technical causes:

1. **Obsolete Model Version Allowlists (7 failures):**
   - **Modules:** `tests.test_ml_pipeline` (3), `tests.test_ml_quality_improvements` (1), `tests.test_ml_remediation` (3).
   - **Mechanism:** Tests assert that loaded model version is one of `['cashout-location-xgb-v4', 'cashout-location-xgb-v3.1', 'cashout-location-xgb-v2', 'cashout-location-xgb-v1']`. The runtime loads the currently promoted `cashout-location-xgb-v7-compat`.
   - **Resolution Target:** Phase 01 (update test fixtures to reflect promoted V7-compat manifest).

2. **Authentication Fixture Omission (27 failures):**
   - **Modules:** `tests.test_step14_auth_audit` (9), `tests.test_step13_dashboard_db_integration` (18).
   - **Mechanism:** Legacy test cases issue unauthenticated GET requests expecting HTTP 200. The application correctly enforces server-side JWT authentication and returns HTTP 401 Unauthorized.
   - **Resolution Target:** Phase 01 (provide valid test tokens in test fixtures; maintain separate unauthenticated 401 tests).

3. **Cross-Test State and Shared Session Interference (25 failures):**
   - **Modules:** `tests.test_step11_gis_persistence_integration` (7), `tests.test_phase3_hotspots_and_gis` (5), `tests.test_dynamic_transaction_graph` (5), `tests.test_transaction_scenario_linking` (8).
   - **Mechanism:** Tests mutate a shared SQLite database instance across cases. For example, `test_phase3_hotspots_and_gis.py` passes 14/14 when executed in isolation, but fails 5 tests when run after earlier modules have modified database state.
   - **Resolution Target:** Phase 01 (per-test rollback/isolation fixtures, dependency override resetting).

4. **Legacy Synthetic Scenario & Seed Fixture Drift (10 failures):**
   - **Modules:** `tests.test_complaint_scenario_linking` (1), `tests.test_synthetic_seed` (1), `tests.test_schema_hardening` (3), `tests.test_step9_prediction_flow` (3), `tests.test_step12_prediction_alert_integration` (2).
   - **Mechanism:** Tests assume pre-existing hardcoded demo entities (e.g. CMP-1042 fallback, synthetic victim accounts, specific record counts) that differ in an unseeded test database.
   - **Resolution Target:** Phase 01.

5. **Timezone / Display Presentation Mismatch (1 failure):**
   - **Module:** `tests.test_delhi_intake_map_regression` (1).
   - **Mechanism:** Test asserts `+00:00` UTC offset in a timestamp string formatted as `18 Sep 2026, 00:22 – 01:22 IST`.
   - **Resolution Target:** Phase 01 (reconcile machine UTC timestamp API contract with IST localized display).

6. **Service-Level Stale Prediction Deduplication (4 failures / reproduced defect):**
   - **Modules:** `tests.test_step10_prediction_persistence` (2), `tests.test_step12_prediction_alert_integration` (2).
   - **Mechanism:** In `prediction_persistence_service.py` (lines 97–115), if a prediction matches the same model mode and rank-1 cluster with 3 locations, the service returns the existing prediction ID even if probabilities for rank-2 or rank-3 have changed.
   - **Resolution Target:** Phase 02 (versioned immutable predictions and cache invalidation).

---

## 5. Confirmed Product Findings and Reproductions

1. **Stale Prediction Result Reuse:**
   - **Evidence:** `scratch/phase0_20260917T175141Z/stale_prediction_reproduction.json`.
   - **Reproduction:** In an isolated test fixture, rank-2 candidate score was updated from `0.0513` to `0.0563` while rank-1 remained identical. Calling `persist_prediction` returned the previous prediction record (`id: 1`) with the old rank-2 score (`0.0513`).
   - **Impact:** Legitimate recalculations following new transactions or updated evidence can be silently ignored if the top candidate cluster does not change.
   - **Status:** Documented for fix in Phase 02.

2. **LIME Explainability Low-Fidelity Label:**
   - **Evidence:** `scratch/phase0_20260917T175141Z/demo_case_snapshot.json` (LIME endpoint).
   - **Observation:** Mean local explanation R² was approximately `0.5061`. The service conservatively flagged this as `low-fidelity`.
   - **Impact:** Does not cause an exception, but indicates that local surrogate models need stability tuning.
   - **Status:** Preserved for Phase 11.

3. **Timing Uncertainty Provenance Gap:**
   - **Observation:** The prediction response contained an operational window (`2–73 min after complaint report`), but `uncertainty_interval` and `timing_basis` fields returned `null`.
   - **Status:** Preserved for Phase 11.

---

## 6. Backup Verification and Checkpoint Integrity

All backups are stored in the git-ignored private directory `scratch/phase0_20260917T175141Z/`. Secret configuration files (`.env`, `frontend/.env`) remain strictly private and are never committed or exposed.

1. **Git Repository Bundle:**
   - **File:** `scratch/phase0_20260917T175141Z/repository.bundle` (6,554,314 bytes).
   - **Verification:** `git bundle verify` confirmed complete commit history across 61 refs.
   - **Restore Drill:** Cleanly cloned into a disposable test directory (`scratch/test_bundle_restore`); checked out commit `90e792eba9f50e135367cf65c3a09658c61471df` with a clean working tree.

2. **Tracked Worktree Zip:**
   - **File:** `scratch/phase0_20260917T175141Z/tracked_worktree.zip` (6,321,382 bytes, 390 tracked files).
   - **Verification:** `ZipFile.testzip()` returned `None` (0 CRC errors).
   - **Restore Drill:** Extracted cleanly to a separate test directory with 31 top-level paths matching project structure.

3. **SQLite Databases (7 files discovered):**
   - Backed up using SQLite's online backup API to `scratch/phase0_20260917T175141Z/sqlite_backups/`.
   - `PRAGMA integrity_check` returned `ok` on all 7 files:
     - `audit_full_suite.db` (16 tables): `ok`
     - `audit_migration_20260917_01.db` (17 tables): `ok`
     - `audit_migration_final_20260917.db` (17 tables): `ok`
     - `ci_final_exact.db` (16 tables): `ok`
     - `cybershield.db` (13 tables): `ok`
     - `phase_2_to_6_ready.db` (16 tables): `ok`
     - `backend/cybershield.db` (0 tables): `ok`

4. **Machine Learning Artifacts:**
   - All 40 files in `ml/artifacts/` were hashed via SHA-256 before and after audit execution.
   - All hashes matched identically (`models_unchanged: true`).

5. **PostgreSQL Read-Only Data Snapshot:**
   - Extracted using `REPEATABLE READ` transaction with `SET TRANSACTION READ ONLY`.
   - 17 tables / 98,259 rows exported into gzip jsonl files (`private_pg_table_001` through `017.jsonl.gz`).
   - All row counts were validated by reopening and counting gzip lines.

---

## 7. Problem Statement Traceability Matrix (PS-01 to PS-25)

The 25 components of the supplied Problem Statement are mapped to actual repository evidence and status as established in Phase 00:

| ID | Problem Statement Requirement / Intent | Current Repository Evidence | Baseline Status | Required Verification / Acceptance Check |
|---|---|---|---|---|
| **PS-01** | Centralized cybercrime reporting portal integration | Complaint APIs and officer UI exist; no verified NCRP live connector | **PARTIAL / EXTERNAL** | Ingest partner sandbox complaint with source reference preserved |
| **PS-02** | National scale (~8,000 complaints daily) | No national concurrency/load benchmark has been executed | **UNVERIFIED** | Throughput, latency, error rate, and recovery under burst load |
| **PS-03** | AI/ML-based predictive system | XGBoost V7-compat location + V3 time model loaded and operational | **TESTED-PROTOTYPE** | Real inference returns persisted ranked locations and model versions |
| **PS-04** | Historical cybercrime and financial data utilization | Synthetic Delhi training files; transaction feature pipeline | **PARTIAL / EXTERNAL** | Provenance report, date splits, leakage checks on real data |
| **PS-05** | Predict potential cash withdrawal hotspots | Fresh case returns Top-3 locations with risk scores and clusters | **TESTED-PROTOTYPE / EXTERNAL** | Top-k recall, distance error, and baseline comparisons on held-out data |
| **PS-06** | Financial pattern detection | Multi-hop transaction graph service and ML feature extraction | **PARTIAL** | Verified transfers drive graph; no synthetic demo chain claimed as live |
| **PS-07** | Geospatial risk modelling | Delhi clusters, coordinates, and candidate generation active | **TESTED-PROTOTYPE** | Regional coverage validated; explicit out-of-scope response for other regions |
| **PS-08** | Real-time actionable intelligence | APIs and WebSocket alerts exist; transaction cutoff <= reported_at | **GAP** | Post-report transfer updates trigger causal, versioned prediction recalculation |
| **PS-09** | Updated intelligence stays accurate | Persistence reuses old prediction if rank-1 matches, even with new scores | **GAP (Reproduction saved)** | Identical request is idempotent; changed input creates traceable new version |
| **PS-10** | GIS-enabled interactive dashboard | Case overlay, hotspot/ATM layers, active/historical separation | **TESTED-PROTOTYPE (API/Build)** | Browser UI renders correct layers and active cases without console errors |
| **PS-11** | Real-time and potential risk zones distinction | Unexpired case predictions separated from historical base layers | **TESTED-PROTOTYPE** | Dedicated GIS module passes 14/14; resolve test state interference |
| **PS-12** | Drill-down by location | District and risk filters implemented in GIS routes | **PARTIAL** | Filter combinations match map/list counts and user jurisdictional scope |
| **PS-13** | Drill-down by time | GET `/api/v1/risk-map` has district/risk_level; lacks time-range query controls | **GAP** | Implement explicit timestamp filtering on API and frontend UI |
| **PS-14** | Drill-down by crime category | Fraud category displayed in details; absent as map filter query param | **GAP** | Add crime category filter affecting clusters and statistics consistently |
| **PS-15** | Secure investigator interface | Server-side JWT auth, RBAC roles, and jurisdiction checks in place | **TESTED-PROTOTYPE** | Comprehensive route audit and object-level authorization tests |
| **PS-16** | Investigator access to alerts | Alerts API, WebSocket push, acknowledgement, and action tracking | **TESTED-PROTOTYPE** | Only authorized officers can retrieve and acknowledge scoped alerts |
| **PS-17** | Intelligence reports | Case intelligence and audit records exist; no full shareable export | **PARTIAL** | Formal report generation including timestamps, model version, and actions |
| **PS-18** | Evidence documentation | Prediction snapshots, audit log entries, and chaincode unit tests | **PARTIAL** | Complete evidence attachment, chain-of-custody, and hashing workflow |
| **PS-19** | Notifications via SMS/email/API OR dashboard | API + WebSocket dashboard triggers functional; SMS/email absent | **PARTIAL (Complies with OR)** | Ensure reliable delivery, retry, and acknowledgement on dashboard/API |
| **PS-20** | Stakeholder routing (LEAs, banks, I4C) | User roles exist for POLICE, BANK, I4C; recipient routing unverified | **PARTIAL** | Scoped routing matrix preventing cross-bank or cross-jurisdiction leakage |
| **PS-21** | Coordination across jurisdictions | Jurisdictional tenancy exists in data schema; cross-state transfer absent | **GAP** | Controlled handoff protocol between originating and destination teams |
| **PS-22** | Deployment of special teams & bank dispatch | Alert escalation and action tracking schema exist; field dispatch unproven | **PARTIAL** | Task assignment, dispatched team recording, and acknowledgement loop |
| **PS-23** | CFCFRMS & bank intelligence for fund blocking | Bank action service simulates lifecycle (`SIMULATED_PENDING_HOLD`) | **EXTERNAL** | Verified sandbox adapter and partner acknowledgement contract |
| **PS-24** | Increasing chances of recovery | Zero measured real-world financial recovery outcomes recorded | **EXTERNAL / UNVERIFIED** | Track holds, releases, and recoveries with auditable proof |
| **PS-25** | Effective proactive response | Synthetic metrics, warning windows, and evaluation artifacts saved | **PARTIAL** | Operational evaluation measuring warning time, false alarm rate, and response |

---

## 8. Pending External Gates

In accordance with strict audit standards, the following gates cannot be claimed as satisfied through local development and are recorded as **PENDING**:

1. **Operational PostgreSQL Native Backup & Isolated Restore Drill (PENDING):**
   - **Configured Engine:** PostgreSQL (`settings.DATABASE_URL`).
   - **Current Status:** A consistent read-only data snapshot (17 tables / 98,259 rows) was secured under `scratch/phase0_20260917T175141Z/`.
   - **Blocker:** Native PostgreSQL backup tooling (`pg_dump`) is not installed on the host system PATH, and the Docker Desktop Linux daemon is currently offline (`//./pipe/dockerDesktopLinuxEngine` not found). Restoring over the live database is prohibited.
   - **Resolution Condition:** Obtain a compatible `pg_dump` binary or start Docker daemon to execute `pg_dump -Fc`, then perform a non-destructive restore into an isolated disposable PostgreSQL database to verify schema, sequences, and row counts.

2. **Authorized External Financial & Law Enforcement Interfaces (PENDING / EXTERNAL):**
   - **CFCFRMS / Bank APIs:** External bank endpoints and auto-freeze execution require official MOU, certificates, and production/sandbox API keys. Local code retains transparent simulation labels.
   - **NCRP Central Intake:** Requires official NIC/I4C portal integration clearance.
   - **SMS / Email Gateway Providers:** Local prototype utilizes dashboard/API notifications; SMS/email gateways remain unconfigured.

3. **Representative National Real-World Cybercrime Dataset (PENDING / EXTERNAL):**
   - Models are trained and evaluated on synthetic Delhi data. Evaluation against out-of-time real cases requires authorized data access.

4. **Multi-Region Geography Expansion (PENDING):**
   - Geographic coverage is explicitly bounded to Delhi NCR. Multi-state coverage requires regional ATM and cluster boundaries.

5. **Browser Visual QA (PENDING):**
   - Production Vite build and TypeScript compilation passed; browser UI visual layout, interactive map rendering, and cross-browser regression testing have not been automated or visually certified.

---

## 9. Rollback Procedure

- **Phase 00 Rollback:**
  - Because Phase 00 made zero modifications to application source files, zero changes to configuration, and zero schema migrations, rollback is trivial:
    ```powershell
    git checkout -- .
    git clean -fd -e scratch/
    ```
- **Disaster Recovery of Pre-Phase 00 State:**
  - If any future phase corrupts repository state or untracked files:
    1. Restore repository history from bundle:
       ```powershell
       git clone scratch/phase0_20260917T175141Z/repository.bundle restored_repo
       ```
    2. Extract clean tracked worktree files from:
       `scratch/phase0_20260917T175141Z/tracked_worktree.zip`
    3. Re-verify SQLite state from:
       `scratch/phase0_20260917T175141Z/sqlite_backups/`
    4. Recover database baseline from:
       `scratch/phase0_20260917T175141Z/private_pg_table_*.jsonl.gz`

---

## 10. Phase Handoff Sign-off

- **Phase 00 Acceptance Criteria:**
  - [x] Checkpoint restoration from `repository.bundle` and `tracked_worktree.zip` to separate directories verified.
  - [x] SQLite backups pass integrity checks (`PRAGMA integrity_check = ok` on all 7 databases).
  - [x] Operational PostgreSQL has read-only snapshot saved; native backup + isolated restore drill explicitly recorded as **PENDING**.
  - [x] Raw test/build outputs and complete 74-item failure catalog retained in `TEST_FAILURES.csv` and `AUDIT_SUMMARY.json`.
  - [x] Browser visual QA explicitly separated from headless build/API evidence.
  - [x] Zero application fixes or model retraining introduced in Phase 00.
  - [x] All 25 Problem Statement items traced with concrete evidence and gaps.
- **Handoff Decision:** Phase 00 is complete. In accordance with the prompt, execution stops here. Do not proceed to Phase 01 without user prompt.
