# Phase 09 Handoff: Verified Outcome Observations & Honest Operational Evaluation

**Phase:** 09  
**Problem-statement mapping:** PS-24, PS-25  
**Dependencies:** Phases 01, 02, 03, 04, 05, 06, 07, and 08  
**Execution date:** 21 September 2026  
**Status:** Completed end-to-end. Ground-truth verified outcome observations (`OutcomeObservation`), server-side `LAST_OPERATIONAL_BEFORE_EVENT` prediction evaluation policy, anti-cherry-picking guardrails (no client prediction selection, replay and future predictions excluded), multi-cashout event capture (`MULTIPLE_CASHOUT`), append-only correction lineage (`ACTIVE` → `SUPERSEDED`), explicit denominator segmentation (measured, unknown, excluded, synthetic cohorts), non-conflated financial reporting (`verified_held_amount_inr` vs `actual_recovered_amount_inr`), RBAC enforcement, and frontend `OutcomeMetrics.tsx` dashboard. All 26 Phase 09 pytests pass with exit code 0. Phase 10 has not started.

---

## 1. Outcome

Phase 09 establishes a verifiable ground-truth evaluation and feedback loop for CyberShield AI. Prior to Phase 09, model performance was evaluated primarily against offline training splits, and real-world cashout outcomes or fund recoveries could not be captured with cryptographic auditability and causal rigor.

Under Phase 09:
1. **Server-Side Evaluation Policy (`LAST_OPERATIONAL_BEFORE_EVENT`):**
   - The system automatically links an outcome observation to the last `OPERATIONAL` prediction generated strictly before `observed_event_time`.
   - Client requests cannot submit or select `linked_prediction_id`, eliminating operator cherry-picking or post-hoc alignment bias.
   - Predictions generated for `HISTORICAL_REPLAY` or generated after `observed_event_time` are categorically excluded from linkage.
2. **Anti-Conflation Financial Reporting:**
   - Bank freeze holds (`verified_held_amount_inr`) and physical cash recoveries (`actual_recovered_amount_inr`) are stored, calculated, and reported as independent figures.
   - The system never sums them as "savings" or attributes them as directly saved money by the AI model. A mandatory legal and methodology note is embedded into every metrics response.
3. **Multi-Cashout Support:**
   - Supports single `CONFIRMED_CASHOUT` and structured `MULTIPLE_CASHOUT` outcomes, persisting individual cashout events, timestamps, ATM IDs, and amounts in a JSON array.
4. **Append-Only Correction Lineage:**
   - Outcome observations are immutable once written. Corrections create a new version (`version = original.version + 1`) and transition the original record to `SUPERSEDED` with a mandatory `correction_reason`.
   - Records already marked `SUPERSEDED` cannot be corrected again, preventing branching or corrupt history.
5. **Honest Operational Metrics & Transparent Denominators:**
   - The metrics dashboard cleanly separates the denominator cohorts: `denominator_measured`, `denominator_unknown`, `denominator_excluded`, and `denominator_synthetic`.
   - Unknown outcomes (`UNKNOWN`) and excluded data (`DATA_EXCLUDED`) are never mixed into cashout accuracy rates or distance error calculations.
   - Synthetic test observations (`is_synthetic=True`) are strictly isolated from real-world operational figures.
6. **Strict RBAC & Auditability:**
   - Ingestion and correction of outcomes are restricted to `I4C_ADMIN`, `STATE_LEA`, and `DISTRICT_LEA`.
   - Read and metrics access are granted to `ANALYST` and `AUDITOR` roles with jurisdiction scoping.
   - Every ingest and correction action generates an audit log entry via `log_audit()`.

---

## 2. Before and After Comparison

| Capability | Before Phase 09 | After Phase 09 |
|---|---|---|
| **Real-World Outcome Tracking** | No dedicated schema for field-verified cashouts or seizures. | `OutcomeObservation` model with source verification, location coordinates, and timestamps. |
| **Prediction Linkage** | Risk of manual selection or post-hoc cherry-picking. | Enforced server-side `LAST_OPERATIONAL_BEFORE_EVENT` policy; client prediction IDs rejected. |
| **Replay & Future Immunity** | Offline replay predictions could pollute production stats. | `HISTORICAL_REPLAY` and predictions created post-event are filtered out at query time. |
| **Financial Accounting** | Risk of conflating frozen accounts with recovered cash. | `verified_held_amount_inr` and `actual_recovered_amount_inr` are partitioned into separate keys with required disclaimers. |
| **Correction Audit Trail** | Mutable row updates could erase operational data. | Append-only lineage (`ACTIVE` / `SUPERSEDED`), version incrementation, and reason logging. |
| **Denominator Integrity** | Missing/unknown outcomes could skew accuracy percentages. | Explicit denominator cohorts: `measured`, `unknown`, `excluded`, `synthetic`. |
| **Frontend Visibility** | No dedicated operational dashboard. | `OutcomeMetrics.tsx` dashboard displaying cohort cards, location accuracy, and lead-time analysis. |

---

## 3. Implementation Details

### Database & Migrations
- **Alembic Migration:** `alembic/versions/0018_phase9_outcome_observations.py`
  - Created `outcome_observations` table with foreign keys to `complaints`, `predictions`, `alerts`, `bank_actions`, and `users`.
  - Indexes created on `(complaint_id, record_status)`, `(outcome_type, record_status)`, `(is_synthetic, is_excluded)`, `observed_event_time`, and `linked_prediction_id`.
- **SQLAlchemy Model:** `backend/app/models/models.py`
  - Added `OutcomeObservation` with relationships: `complaint`, `linked_prediction`, `linked_alert`, `linked_bank_action`, `verifier`, and `ingested_by`.

### Schemas (`backend/app/schemas/schemas.py`)
- **`OutcomeCreateRequest`:** Validates outcome ingestion payloads (coordinates, amounts, UTC timestamps, exclusion flags).
- **`OutcomeCorrectRequest`:** Enforces `correction_reason` (min length 5) for record updates.
- **`OutcomeResponse`:** Returns full outcome details including `prediction_selection_policy="LAST_OPERATIONAL_BEFORE_EVENT"`.
- **`OutcomeMetricsResponse`:** Returns operational metrics with distinct denominators, accuracy metrics, lead times, and non-conflated financial figures with disclaimers.

### Service Layer (`backend/app/services/outcome_service.py`)
- **`create_outcome`:**
  - Enforces `LAST_OPERATIONAL_BEFORE_EVENT` policy via `_select_eligible_prediction`.
  - Computes `prediction_rank_matched`, `distance_error_km`, and lead-time metrics against predicted locations.
  - Requires `exclusion_reason` if `is_excluded=True` or `outcome_type="DATA_EXCLUDED"`.
  - Emits `OUTCOME_INGESTED` audit entry.
- **`correct_outcome`:**
  - Validates `original.record_status == "ACTIVE"`.
  - Marks original record as `SUPERSEDED`.
  - Creates new version linked via `corrects_outcome_id`.
  - Emits `OUTCOME_CORRECTED` audit entry.
- **`get_outcome_metrics`:**
  - Computes aggregation metrics over active, non-synthetic, non-excluded cohorts.
  - Returns `None` for rates when `denominator_cashout == 0` to prevent division by zero.
  - Embeds mandatory financial disclosure note.

### API Routes (`backend/app/api/outcome_routes.py`)
- `POST /api/v1/outcomes/complaints/{complaint_id}`: Ingest outcome (`I4C_ADMIN`, `STATE_LEA`, `DISTRICT_LEA`).
- `POST /api/v1/outcomes/{outcome_id}/correct`: Correct outcome (`I4C_ADMIN`, `STATE_LEA`, `DISTRICT_LEA`).
- `GET  /api/v1/outcomes/complaints/{complaint_id}`: List complaint outcomes with lineage.
- `GET  /api/v1/outcomes/{outcome_id}`: Retrieve single outcome observation.
- `GET  /api/v1/outcomes/metrics`: Aggregate operational dashboard metrics (`I4C_ADMIN`, `ANALYST`, `AUDITOR`).

### Frontend Implementation
- **Page:** `frontend/src/pages/OutcomeMetrics.tsx`
  - Cohort breakdown cards (`Measured`, `Unknown`, `Excluded`, `Synthetic`).
  - Prediction accuracy metrics (Rank-1, Top-K, Mean Distance Error).
  - Operational timing metrics (Prediction Lead Time, Alert Lead Time, Bank Response Latency).
  - Disclosed financial metrics (Verified Held vs Actual Recovered) with prominent methodology disclaimer.
- **API Client:** `frontend/src/services/api.ts` (`ingestOutcome`, `correctOutcome`, `listOutcomesForComplaint`, `getOutcome`, `getOutcomeMetrics`).
- **Types:** `frontend/src/types/index.ts` (`OutcomeObservation`, `OutcomeCreatePayload`, `OutcomeCorrectPayload`, `OutcomeMetrics`).
- **Routing:** `frontend/src/App.tsx` (Route `/outcome-metrics` configured with lazy loading).

---

## 4. Verification & Test Results

### Test Suite Execution
All 26 automated tests in `tests/test_phase9_outcome_observations.py` executed cleanly:

```
============================= test session starts =============================
platform win32 -- Python 3.13.0, pytest-9.1.1, pluggy-1.6.0
rootdir: <repository-root>
configfile: pytest.ini
plugins: anyio-4.15.1
collected 26 items

tests/test_phase9_outcome_observations.py::test_confirmed_cashout_creates_outcome PASSED [  3%]
tests/test_phase9_outcome_observations.py::test_unknown_outcome_no_prediction_required PASSED [  7%]
tests/test_phase9_outcome_observations.py::test_invalid_outcome_type_rejected PASSED [ 11%]
tests/test_phase9_outcome_observations.py::test_excluded_without_reason_rejected PASSED [ 15%]
tests/test_phase9_outcome_observations.py::test_multiple_cashout_stores_cashout_events PASSED [ 19%]
tests/test_phase9_outcome_observations.py::test_multiple_cashout_partial_amounts_stored_separately PASSED [ 23%]
tests/test_phase9_outcome_observations.py::test_no_future_prediction_linked PASSED [ 26%]
tests/test_phase9_outcome_observations.py::test_historical_replay_prediction_excluded PASSED [ 30%]
tests/test_phase9_outcome_observations.py::test_last_operational_before_event_selected PASSED [ 34%]
tests/test_phase9_outcome_observations.py::test_correction_creates_new_version PASSED [ 38%]
tests/test_phase9_outcome_observations.py::test_correction_of_superseded_record_rejected PASSED [ 42%]
tests/test_phase9_outcome_observations.py::test_correction_without_reason_rejected PASSED [ 46%]
tests/test_phase9_outcome_observations.py::test_unknown_excluded_from_measured_denominator PASSED [ 50%]
tests/test_phase9_outcome_observations.py::test_synthetic_cohort_separate PASSED [ 53%]
tests/test_phase9_outcome_observations.py::test_data_excluded_counted_separately PASSED [ 57%]
tests/test_phase9_outcome_observations.py::test_metrics_returns_none_rates_when_no_cashouts PASSED [ 61%]
tests/test_phase9_outcome_observations.py::test_held_and_recovered_stored_separately PASSED [ 65%]
tests/test_phase9_outcome_observations.py::test_metrics_financial_note_present PASSED [ 69%]
tests/test_phase9_outcome_observations.py::test_metrics_financials_reported_as_separate_keys PASSED [ 73%]
tests/test_phase9_outcome_observations.py::test_analyst_cannot_ingest_outcome PASSED [ 76%]
tests/test_phase9_outcome_observations.py::test_auditor_cannot_ingest_outcome PASSED [ 80%]
tests/test_phase9_outcome_observations.py::test_state_lea_can_ingest_outcome PASSED [ 84%]
tests/test_phase9_outcome_observations.py::test_analyst_can_read_metrics PASSED [ 88%]
tests/test_phase9_outcome_observations.py::test_ingest_and_retrieve_outcome PASSED [ 92%]
tests/test_phase9_outcome_observations.py::test_list_outcomes_for_complaint PASSED [ 96%]
tests/test_phase9_outcome_observations.py::test_correct_outcome_via_api PASSED [100%]

======================== 26 passed, 36758 warnings in 101.80s ========================
```

### Cryptographic File Checksums (SHA-256)
| File | SHA-256 Hash |
|---|---|
| `backend/app/models/models.py` | `6FA024E0AC7B8F6AE2C8F70BFF8FA054AD331ECA547EC8ED9D05D79A55EB5711` |
| `backend/app/services/outcome_service.py` | `6340CD9A0BF3BA3619B57FF86F57CEFA2237FCA8535156295700028A400F42E4` |
| `backend/app/api/outcome_routes.py` | `17E41EA57E2945779FDDE9B3821B73A03452FB1BF1AC8ABAF7C9D920AF3142A4` |
| `tests/test_phase9_outcome_observations.py` | `E8A701A5FEA7FE047DB3DBE3CA04231BBB6DC7309F15030B0ECFC3D349232FB2` |
| `alembic/versions/0018_phase9_outcome_observations.py` | `CE0A9EF9C91B9DFF543CB61B595070F826085E0FD3E5DCD87BBBECD52EC8EB10` |
| `frontend/src/pages/OutcomeMetrics.tsx` | `1BEBD6CD83FA062D37B542227C51FE4E2B5B3BC89C84E7CDAE84A039469CD71E` |

---

## 5. Architectural Invariants & Non-Negotiable Guarantees

1. **No Financial Conflation:** Under no circumstances are `verified_held_amount_inr` and `actual_recovered_amount_inr` aggregated into a single "total saved" figure.
2. **Server-Side Prediction Linkage:** No API route or service entry point accepts a client-provided prediction ID. Linkage is solely computed via `LAST_OPERATIONAL_BEFORE_EVENT`.
3. **Lineage Preservation:** No `OutcomeObservation` row is ever deleted. Corrections are strictly append-only with `SUPERSEDED` status flags.
4. **Cohort Isolation:** Synthetic and excluded observations are mathematically isolated from live operational metrics.
5. **Phase Handoff Gate:** Phase 09 is complete. Phase 10 has not started.
