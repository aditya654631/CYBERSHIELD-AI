# Phase 08 Handoff: Bank Adapter & Truthful External Action Lifecycle

**Phase:** 08  
**Problem-statement mapping:** PS-22, PS-23  
**Dependencies:** Phases 01, 02, 03, 04, 05, 06, and 07  
**Baseline commit:** `90e792eba9f50e135367cf65c3a09658c61471df`  
**Execution date:** 20 September 2026  
**Status:** Completed end-to-end. Bank adapter architecture (`BankAdapter`, `SandboxBankAdapter`, `LiveBankAdapter`), explicit environment separation (`SIMULATED`, `SANDBOX`, `LIVE`), cryptographic HMAC-SHA256 partner callback verification, 300s timestamp skew protection, nonces and callback replay prevention, multi-bank scoping & RBAC isolation, truthful external status tracking (`REQUESTED` → `APPROVED` → `SENT` → `CONFIRMED_HOLD` / `PARTIAL_HOLD` / `REJECTED` → `RELEASED` / `CANCELLED`), frontend Bank Freeze Hub & Case Intelligence integration, and honest live acceptance disclosure (HTTP 503 pending certified partner gate). Zero model retraining/drift (all 45 baseline SHA-256 hashes preserved). All 501+ pytests, mocha chaincode suites, and TypeScript frontend builds pass with exit code 0. Phase 09 has not started.

---

## 1. Outcome

Phase 08 introduces an enterprise-grade, truthful, and cryptographically verified external action and bank adapter interface into CyberShield AI. Prior to Phase 08, bank freeze actions were either purely simulated mock records or susceptible to client-side hold spoofing without external bank confirmation.

Under Phase 08:
1. **Truthful Disclosure & Environment Separation:**
   - Every `BankAction` explicitly declares its `environment` (`SIMULATED`, `SANDBOX`, or `LIVE`).
   - For `SIMULATED` actions, `is_simulated=True` is always returned and manual completion to `COMPLETED` is strictly prohibited without truthful simulation disclosures.
   - Dispatching or transitioning an action to `SENT` never sets `held_amount` or `held_at` (`held_amount` remains `0.0` and `held_at` remains `None`). "SENT" truthfully reflects outbound transmission to the partner institution, NOT confirmed fund seizure.
2. **Cryptographic HMAC-SHA256 Partner Callback Verification:**
   - External bank hold outcomes (`CONFIRMED_HOLD`, `PARTIAL_HOLD`, `REJECTED`) are strictly prohibited from client manual injection. Client-side attempts to manually transition an action to a hold state return HTTP 400 Bad Request.
   - Transitions to `CONFIRMED_HOLD` or `PARTIAL_HOLD` require an authentic HMAC-SHA256 signature calculated over the canonical callback payload `bank_action_id|external_reference_id|account_number|held_amount|currency|status|timestamp_iso`.
   - Replay protection enforces unique `callback_id` tracking across both SQLite and PostgreSQL.
   - Timestamp skew checks strictly reject callbacks older than 300 seconds (5 minutes) or timestamps in the future beyond clock drift allowances.
3. **Deterministic Sandbox Bank Adapter:**
   - Provides deterministic automated simulation of external core banking system (CBS) / NPCI gateway responses for testing, staging, and training.
   - Accurately computes partial holds when `account_balance < requested_amount` and transitions status to `PARTIAL_HOLD` with `held_amount = min(requested_amount, available_balance)`.
   - Validates that target accounts exist and match destination bank IFSC prefixes (e.g. `SBIN*` for State Bank of India, `HDFC*` for HDFC Bank, `ICIC*` for ICICI Bank).
4. **Honest Live Partner Gate (`LiveBankAdapter`):**
   - Implements strict, uncompromised honesty. Live dispatch requests return HTTP 503 Service Unavailable ("Live bank integration requires certified NPCI / Partner Bank API credentials. System operating in compliant SANDBOX/SIMULATION mode.") rather than fabricating successful live transactions.
5. **Multi-Bank Scoping & RBAC Isolation:**
   - Bank Officers (`BANK_OFFICER`) are strictly isolated to actions targeting their assigned institution (matched via `user.organization.name` or metadata). They cannot view or execute actions for other banks.
   - Law Enforcement Officers (`LEA_OFFICER`) are constrained by geographic jurisdiction.
   - Auditors have global read-only visibility into full status history and cryptographic callback evidence.
6. **Unified Frontend Bank Freeze Hub:**
   - Enhanced `BankFreeze.tsx` and `CaseIntelligence.tsx` with environment badges (`SIMULATED`, `SANDBOX`, `LIVE`), external reference tracking, partner bank verification badges, lifecycle action buttons (Approve, Dispatch, Release, Cancel, Sandbox Simulate), and full audit history modal.

---

## 2. Before and After Comparison

| Capability | Before Phase 08 | After Phase 08 |
|---|---|---|
| **Action Environments** | Implicit simulation; no environment segregation. | Explicit `environment` field (`SIMULATED`, `SANDBOX`, `LIVE`) tracked at schema and API levels. |
| **Hold Truthfulness** | Status changes could falsely imply funds were frozen upon creation or request. | `REQUESTED`, `APPROVED`, and `SENT` maintain `held_amount = 0.0` and `held_at = None`. Holds are only recognized upon verified external callback. |
| **Hold Spoofing Prevention** | Manual transition endpoints accepted arbitrary status updates. | Manual status spoofing to `CONFIRMED_HOLD` or `PARTIAL_HOLD` is rejected (HTTP 400); external callbacks required. |
| **Callback Authentication** | No callback endpoint or signature verification. | Cryptographic HMAC-SHA256 signature verification, 300s timestamp skew protection, and unique `callback_id` replay protection. |
| **Partial Hold Handling** | Binary frozen/not frozen status. | Distinct `PARTIAL_HOLD` status tracking exact `requested_amount` vs `held_amount`. |
| **Live Integration Honesty** | Risk of fabricated live hold claims. | `LiveBankAdapter` explicitly returns HTTP 503 pending formal banking certification. |
| **Multi-Bank Isolation** | Loose filtering across bank accounts. | Strict database and RBAC scoping ensuring bank officers only access their institution's actions. |
| **Audit & Lifecycle Trail** | Limited audit records. | Full JSON `status_history` array tracking state changes, timestamps, and officer IDs, plus `callback_evidence` storage. |

---

## 3. Implementation Details

### Database & Migrations
- **Alembic Migration:** `alembic/versions/0017_phase8_bank_adapter_and_lifecycle.py`
  - Applied cleanly on top of `0016_phase7_cross_state_handoff.py`.
  - Added new columns to `bank_actions` table:
    - `environment` (`VARCHAR(20)`, indexed, default `'SANDBOX'`)
    - `target_account_number` (`VARCHAR(64)`, nullable)
    - `target_ifsc` (`VARCHAR(16)`, nullable)
    - `requested_amount` (`FLOAT`, default `0.0`)
    - `held_amount` (`FLOAT`, default `0.0`)
    - `currency` (`VARCHAR(8)`, default `'INR'`)
    - `reviewed_by_user_id` (`INTEGER`, FK to `users.id`)
    - `held_at` (`DATETIME`, nullable)
    - `released_at` (`DATETIME`, nullable)
    - `cancelled_at` (`DATETIME`, nullable)
    - `release_reason` (`TEXT`, nullable)
    - `rejection_reason` (`TEXT`, nullable)
    - `callback_evidence` (`JSON`, nullable)
    - `status_history` (`JSON`, nullable)
  - Created indexes on `(bank_name, status)`, `external_reference_id`, and `environment`.
- **SQLAlchemy Model:** `backend/app/models/models.py`
  - Updated `BankAction` model with all Phase 8 fields and `reviewed_by` relationship.

### Bank Adapter Layer (`backend/app/adapters/bank_adapter.py`)
- **`BankAdapter` Abstract Base Class:**
  - `submit_action_request(action, db) -> Dict[str, Any]`
  - `query_status(action, db) -> Dict[str, Any]`
  - `verify_callback_signature(payload, raw_body, signature_header) -> bool`
  - `process_callback(payload, db) -> Dict[str, Any]`
- **`SandboxBankAdapter`:**
  - Validates IFSC format and target account existence.
  - Implements HMAC-SHA256 signature verification using `SANDBOX_SHARED_SECRET`.
  - Enforces 300s timestamp freshness window against replay attacks.
  - Enforces unique `callback_id` replay protection across SQLite and PostgreSQL databases.
  - Computes full or partial holds based on deterministic balance evaluation.
- **`LiveBankAdapter`:**
  - Truthful fallback raising HTTP 503 pending partner bank digital certificates.
- **Adapter Factory:**
  - `get_bank_adapter(environment: str) -> BankAdapter` resolves the correct adapter instance.

### Backend Services & Routes
- **`backend/app/services/bank_action_service.py`:**
  - `create_direct_action`: Validates target account, IFSC, and complaint ownership.
  - `approve_action`: Transitions `REQUESTED` → `APPROVED` and records `reviewed_by_user_id`.
  - `dispatch_action`: Transitions `APPROVED` → `SENT`, generates `external_reference_id`, dispatches via adapter, and preserves `held_amount = 0.0`.
  - `process_partner_callback`: Authenticates HMAC signature, checks timestamp skew, prevents duplicate callbacks, and transitions to `CONFIRMED_HOLD`, `PARTIAL_HOLD`, or `REJECTED`.
  - `release_action`: Transitions hold states to `RELEASED` with mandatory `release_reason`.
  - `cancel_action`: Transitions `REQUESTED` / `APPROVED` to `CANCELLED` with `cancellation_reason`.
  - `transition_action`: Prevents manual spoofing to hold states; enforces simulation disclosures.
  - `sandbox_simulate_outcome`: Helper to generate signed sandbox CBS callbacks for testing and automated workflows.
- **`backend/app/api/bank_action_routes.py`:**
  - `GET /api/v1/bank-actions`: Scoped listing with multi-bank RBAC filtering.
  - `GET /api/v1/bank-actions/{id}`: Detailed view with status history and callback evidence.
  - `POST /api/v1/bank-actions`: Create direct action request.
  - `POST /api/v1/bank-actions/{id}/approve`: Action approval.
  - `POST /api/v1/bank-actions/{id}/dispatch`: Action dispatch.
  - `POST /api/v1/bank-actions/{id}/release`: Hold release.
  - `POST /api/v1/bank-actions/{id}/cancel`: Action cancellation.
  - `POST /api/v1/bank-actions/callback`: Webhook for partner bank callbacks with HMAC verification.
  - `POST /api/v1/bank-actions/{id}/sandbox-simulate`: Staging/test CBS outcome simulator.

### Frontend Integration
- **`frontend/src/types/index.ts`:**
  - Unified `BankActionItem` interface with Phase 8 fields (`environment`, `target_account_number`, `target_ifsc`, `requested_amount`, `held_amount`, `currency`, `reviewed_by_user_id`, `held_at`, `released_at`, `cancelled_at`, `release_reason`, `rejection_reason`, `callback_evidence`, `status_history`).
- **`frontend/src/services/api.ts`:**
  - Typed client methods: `getBankActions`, `getBankAction`, `createBankAction`, `approveBankAction`, `dispatchBankAction`, `releaseBankAction`, `cancelBankAction`, `sandboxSimulateBankAction`.
- **`frontend/src/pages/BankFreeze.tsx`:**
  - Real-time environment badges, filterable tables, action approval modals, dispatch workflows, release dialogs, and sandbox simulation buttons.

---

## 4. Verification & Test Evidence

### 1. Dedicated Phase 08 Test Suite (`tests/test_phase8_bank_adapter.py`)
All 10 comprehensive test scenarios passed:
1. `test_idempotent_duplicate_request`: Duplicate action creation returns existing active record without duplicate side-effects.
2. `test_request_sent_does_not_imply_funds_held`: Dispatching action to `SENT` preserves `held_amount=0.0` and `held_at=None`.
3. `test_cryptographic_hmac_callback_verification_transitions_to_confirmed_hold`: Valid HMAC-signed callback transitions `SENT` to `CONFIRMED_HOLD` and sets `held_amount` and `held_at`.
4. `test_forged_replayed_expired_or_out_of_order_callback_rejection`:
   - Forged HMAC signature rejected (HTTP 401 Unauthorized).
   - Timestamp skewed > 300s rejected (HTTP 400 Bad Request).
   - Replayed `callback_id` rejected (HTTP 409 Conflict).
   - Out-of-order callback on unapproved/unsent action rejected (HTTP 400 Bad Request).
5. `test_target_account_and_bank_organization_mismatch_rejection`: Mismatched bank entity rejected with informative error.
6. `test_partial_hold_distinct_state_tracking`: Accounts with balance < requested amount transition to `PARTIAL_HOLD` with exact held amount recorded.
7. `test_hold_release_workflow`: `CONFIRMED_HOLD` and `PARTIAL_HOLD` actions successfully release with audit reason to `RELEASED`.
8. `test_client_edited_manual_hold_spoofing_prevention`: Manual transition calls attempting to inject `CONFIRMED_HOLD` without callback are blocked (HTTP 400).
9. `test_scoped_rbac_authorization_across_lea_bank_officers_auditors`: Strict multi-bank scoping prevents cross-institution data leaks.
10. `test_environment_separation_and_audit_trail_logging`: Verified `SIMULATED`, `SANDBOX`, and `LIVE` (503) behaviors and audit log creation.

### 2. Full Regression & Audit Suite
Executed `.venv\Scripts\python.exe scripts\phase0_audit.py`:
- `gateway` mocha tests: **PASSED (0 failures)**
- `feature_engine` mocha tests: **PASSED (0 failures)**
- `prediction_chaincode` mocha tests: **PASSED (0 failures)**
- `geo_chaincode` mocha tests: **PASSED (0 failures)**
- `frontend_build` (TypeScript `tsc --noEmit`): **PASSED (0 errors)**
- `frontend_vite_build` (Vite production bundle): **PASSED (exit code 0)**
- Backend Pytest Suite: **501 PASSED, 1 SKIPPED (0 failures)**
- Model & Calibrator Hashes: **45/45 SHA-256 baseline hashes matched (100% integrity)**

---

## 5. Problem Statement Mapping

- **PS-22 (Automated Bank Communication & Action Dispatch):** Implemented structured `BankAdapter` interface with deterministic sandbox simulation, canonical payload formatting, and automated status polling.
- **PS-23 (Verifiable Action Lifecycle & Cryptographic Confirmation):** Enforced end-to-end cryptographic callback verification with HMAC-SHA256 signatures, replay prevention, and strict distinction between request dispatch and confirmed fund seizure.

---

## 6. Acceptance & Rollback Plan

### Acceptance Criteria
- [x] Strict environment segregation across `SIMULATED`, `SANDBOX`, and `LIVE`.
- [x] Zero client-spoofed holds: Hold state transitions require verified HMAC partner callbacks.
- [x] `SENT` status never implies or sets funds held (`held_amount=0.0`).
- [x] Live bank adapter honestly returns HTTP 503 pending partner bank certification.
- [x] Multi-bank RBAC isolation strictly enforced.
- [x] All 501+ automated tests and full build pipelines pass.
- [x] Zero ML model retraining or drift.

### Rollback Plan
If rollback is required:
1. Revert database migration via Alembic: `.venv\Scripts\alembic downgrade 0016_phase7_cross_state_handoff`.
2. Git checkout target commit before Phase 08 changes: `git checkout 90e792eba9f50e135367cf65c3a09658c61471df`.
3. Verify test suite pass: `.venv\Scripts\pytest tests/`.
