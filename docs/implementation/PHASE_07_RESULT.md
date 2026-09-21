# Phase 07 Handoff: Controlled Cross-State & Cross-District Case Handoff & Scoped Assignments

**Phase:** 07  
**Problem-statement mapping:** PS-03, PS-06, PS-13, PS-18, PS-24  
**Dependencies:** Phases 01, 02, 03, 04, 05, and 06  
**Baseline commit:** `90e792eba9f50e135367cf65c3a09658c61471df`  
**Execution date:** 20 September 2026  
**Status:** Completed end-to-end for explicit cross-jurisdiction case handoff records, state machine lifecycle management (`REQUESTED → ACCEPTED / REJECTED → IN_PROGRESS → COMPLETED / CANCELLED`), trusted destination organization resolution, time-bounded scoped evidence and case visibility, automatic deadline expiry, durable escalation alerts, and frontend Case Intelligence task assignment workflow. Zero model retraining/drift (all 45 baseline SHA-256 hashes preserved). Phase 08 has not started.

---

## 1. Outcome

CyberShield AI now provides a controlled, secure, and auditable cross-state and cross-district case handoff system. When a cyber financial fraud incident originates in one jurisdiction (e.g., Delhi) but actionable intelligence (such as mule account withdrawal ATM hotspots or suspect physical presence) falls in another jurisdiction (e.g., Mumbai, Maharashtra), the originating LEA can issue an explicit task assignment.

The case-owning jurisdiction remains strictly separate from the predicted-action jurisdiction. The destination law enforcement team does not gain unfettered access or ownership over the case; instead, they receive a time-bounded, scoped grant restricted to the minimum required evidence (`METADATA_ONLY`, `SPECIFIC_EVIDENCE`, or `ALL_EVIDENCE`). 

All transitions follow a formal state machine with full audit logging, acknowledgement deadlines, auto-expiration on timeout with Phase 05 durable escalation alerts, and immediate access revocation upon rejection, cancellation, completion, or expiration.

### Key Capabilities Delivered:

1. **Explicit Case Handoff Schema (`case_handoffs`):**
   - Database table `case_handoffs` tracking:
     - `id`, `complaint_id`, `prediction_id`, `prediction_version`
     - `origin_organization_id`, `destination_organization_id`, `target_state`, `target_district`
     - `purpose` (`PHYSICAL_SURVEILLANCE`, `ATM_INTERCEPTION`, `MULE_ARREST`, `EVIDENCE_COLLECTION`, `BANK_BRANCH_VISIT`, `LOCAL_INQUIRY`, `OTHER`)
     - `evidence_scope` (`METADATA_ONLY`, `SPECIFIC_EVIDENCE`, `ALL_EVIDENCE`)
     - `shared_evidence_ids` (JSON array of specific evidence file IDs)
     - `status` (`REQUESTED`, `ACCEPTED`, `REJECTED`, `IN_PROGRESS`, `COMPLETED`, `CANCELLED`, `EXPIRED`)
     - `initiator_user_id`, `recipient_user_id`
     - `created_at`, `updated_at`, `accepted_at`, `completed_at`, `cancelled_at`, `acknowledgement_deadline`
     - `rejection_reason`, `cancellation_reason`, `completed_notes`

2. **Trusted Destination Organization Resolution:**
   - Client requests cannot arbitrary inject or self-grant destination access.
   - `resolve_destination_organization(...)` strictly matches target state and district against registered, verified `Organization` entities with `org_type == 'LEA'`.
   - Rejects attempts to self-handoff to the originating organization.

3. **Strict State Machine Lifecycle & Concurrency Protection:**
   - Valid transition paths:
     - `REQUESTED` → `ACCEPTED` (binds recipient officer)
     - `REQUESTED` → `REJECTED` (with mandatory rejection reason)
     - `REQUESTED` / `ACCEPTED` → `CANCELLED` (by originating team with reason)
     - `REQUESTED` → `EXPIRED` (when acknowledgement deadline passes without acceptance)
     - `ACCEPTED` → `IN_PROGRESS` (marks fieldwork begun)
     - `IN_PROGRESS` → `COMPLETED` (with completion findings notes)
     - `IN_PROGRESS` → `CANCELLED` (originator revocation)
   - Idempotent duplicate requests: Replaying identical actions by the assigned officer returns HTTP 200 safely.
   - Concurrent acceptance protection: If Officer A accepts a handoff, a subsequent attempt by Officer B from the same organization receives HTTP 409 Conflict.

4. **Time-Bounded Scoped Jurisdictional Access & Evidence Scoping:**
   - RBAC rules in `backend/app/auth/rbac.py` updated:
     - Active handoffs (`REQUESTED`, `ACCEPTED`, `IN_PROGRESS`) grant scoped visibility of the assigned complaint to officers of the destination organization.
     - Originating team retains full case ownership (`owner_organization_id`).
     - Unrelated jurisdictions (e.g. Bangalore LEA) and bank officers cannot discover or access handed-off cases (HTTP 404).
   - Evidence scoping in `backend/app/api/evidence_routes.py`:
     - `METADATA_ONLY`: Destination officer can list evidence metadata but file downloads are blocked (HTTP 403).
     - `SPECIFIC_EVIDENCE`: Only evidence IDs listed in `shared_evidence_ids` are visible or downloadable.
     - `ALL_EVIDENCE`: All active evidence files associated with the complaint are accessible during the active handoff window.

5. **Access Revocation on Rejection, Cancellation, Expiration, or Completion:**
   - Once a handoff is `REJECTED`, `CANCELLED`, or `EXPIRED`, destination organization access is instantly revoked across all endpoints (Complaint list, detail, graph, transactions, evidence, and report).

6. **Acknowledgement Deadlines & Durable Escalation Alerts:**
   - Every handoff request establishes an `acknowledgement_deadline` (default 24h, configurable).
   - Background/scheduled endpoint `POST /api/v1/handoffs/check-expirations` identifies overdue requests, marks them `EXPIRED`, and enqueues high-priority Phase 05 durable escalation alerts to the originating organization.

7. **Frontend Case Intelligence Handoff Workflow:**
   - Integrated into existing `CaseIntelligence.tsx` (no disconnected separate portal).
   - "Cross-Jurisdiction Task Assignments" section displaying active handoffs with status badges, purpose, evidence scope, deadline countdown, and action buttons.
   - "Initiate Cross-State Task" modal allowing selection of target state, district, purpose, evidence scope, and acknowledgement window.
   - Action confirmation modals for Accept, Reject, Start Progress, Complete, and Cancel.

---

## 2. Before and After Comparison

| Area | Before Phase 07 | After Phase 07 |
|---|---|---|
| **Cross-Jurisdiction Action** | Cases were strictly isolated by state/district with no mechanism to coordinate cross-state interception without transferring whole case ownership. | Controlled task assignments (`CaseHandoff`) allow originating team to delegate physical/interception tasks while retaining full case ownership. |
| **Destination Access Control** | Binary access: either full case access or total 404 isolation. | Granular, scoped, and time-bounded access based on explicit `evidence_scope` (`METADATA_ONLY`, `SPECIFIC_EVIDENCE`, `ALL_EVIDENCE`). |
| **Destination Resolution** | No entity resolution for external LEAs. | Strict database-backed resolution against verified LEA organizations preventing unauthorized access grants. |
| **State Tracking** | No lifecycle tracking for inter-agency coordination. | Formal state machine (`REQUESTED → ACCEPTED / REJECTED → IN_PROGRESS → COMPLETED / CANCELLED / EXPIRED`) with concurrency conflict protection (409). |
| **Escalation & SLA** | No SLA tracking for inter-agency tasks. | Configurable acknowledgement deadlines with automatic expiration and Phase 05 durable escalation outbox alerts. |
| **Investigator UI** | Case Intelligence only allowed viewing single-jurisdiction data. | Built-in Cross-Jurisdiction Task Assignments table and modal dialogs directly inside Case Intelligence. |

---

## 3. Implementation Details

### Database & Migrations
- `backend/app/models/models.py`:
  - Added `CaseHandoff` model with foreign keys to `complaints.id`, `organizations.id` (origin and destination), `users.id` (initiator and recipient), `predictions.id`.
  - Added `handoffs` relationship on `Complaint`.
- `alembic/versions/0016_phase7_cross_state_handoff.py`:
  - Created migration creating `case_handoffs` table with indexes on `(complaint_id, destination_organization_id, status)` and `acknowledgement_deadline`.

### Backend Services & Routes
- `backend/app/auth/rbac.py`:
  - Updated `_filter_geographic_scope` and `filter_complaints_by_jurisdiction` to include complaints with active handoffs (`status IN ('REQUESTED', 'ACCEPTED', 'IN_PROGRESS')`) targeted to `user.organization_id`.
  - Added `get_active_complaint_handoff(complaint_id, user, db)` helper for downstream route-level evidence scope checks.
- `backend/app/services/handoff_service.py`:
  - `resolve_destination_organization(...)`: Resolves trusted LEA organizations by district/state.
  - `request_case_handoff(...)`: Validates input, builds deadline, checks evidence IDs, persists handoff, logs audit event.
  - `accept_case_handoff(...)`: Binds recipient officer, validates state transition, prevents concurrent conflict (HTTP 409).
  - `reject_case_handoff(...)`: Records rejection reason, logs audit event, revokes access.
  - `start_case_handoff(...)`: Transitions `ACCEPTED` → `IN_PROGRESS`.
  - `complete_case_handoff(...)`: Records completion notes, logs audit event.
  - `cancel_case_handoff(...)`: Originator cancels request with reason.
  - `check_and_expire_handoffs(...)`: Batch expires overdue handoffs and enqueues Phase 05 durable alerts.
- `backend/app/api/handoff_routes.py`:
  - `POST /api/v1/complaints/{id}/handoffs`: Request handoff.
  - `GET /api/v1/complaints/{id}/handoffs`: List case handoffs.
  - `GET /api/v1/handoffs/incoming`: List incoming handoffs for current user's organization.
  - `GET /api/v1/handoffs/outgoing`: List outgoing handoffs from current user's organization.
  - `GET /api/v1/handoffs/{id}`: Handoff detail.
  - `POST /api/v1/handoffs/{id}/accept`: Accept handoff.
  - `POST /api/v1/handoffs/{id}/reject`: Reject handoff.
  - `POST /api/v1/handoffs/{id}/start`: Start task.
  - `POST /api/v1/handoffs/{id}/complete`: Complete task.
  - `POST /api/v1/handoffs/{id}/cancel`: Cancel handoff.
  - `POST /api/v1/handoffs/check-expirations`: Trigger expiration check.
- `backend/app/api/evidence_routes.py`:
  - Updated `list_complaint_evidence`, `get_evidence_detail`, and `download_evidence_file` to enforce active handoff evidence scope (`METADATA_ONLY` blocks download, `SPECIFIC_EVIDENCE` restricts to shared IDs).
- `backend/app/main.py`:
  - Registered `handoff_router` under `/api/v1`.

### Frontend Implementation
- `frontend/src/types/index.ts`: Added `CaseHandoffItem`, `CreateHandoffPayload`.
- `frontend/src/services/api.ts`: Added `getComplaintHandoffs`, `createCaseHandoff`, `getIncomingHandoffs`, `getOutgoingHandoffs`, `acceptHandoff`, `rejectHandoff`, `startHandoff`, `completeHandoff`, `cancelHandoff`.
- `frontend/src/pages/CaseIntelligence.tsx`:
  - Added Cross-Jurisdiction Task Assignments table showing status, purpose, scope, deadline countdown, and action buttons.
  - Added "Initiate Cross-State Task" modal and action confirmation modal.
  - Verified frontend build (`tsc` and `vite build`) exit code 0.

---

## 4. Problem Statement (PS) Traceability

- **PS-03 (Cross-Jurisdiction Collaboration):** Implemented explicit task assignment mechanism enabling inter-state and inter-district law enforcement coordination.
- **PS-06 (Data Privacy & Scoped Sharing):** Enforced minimum necessary evidence sharing (`METADATA_ONLY`, `SPECIFIC_EVIDENCE`, `ALL_EVIDENCE`) and strict access revocation upon task conclusion.
- **PS-13 (Audit Trail & Accountability):** Immutable audit log records for every handoff transition with initiator, recipient, timestamp, and justification.
- **PS-18 (Role-Based Access Control):** Preserved strict jurisdictional boundary rules while allowing explicit time-bounded delegation.
- **PS-24 (Operational Workflow Integration):** Integrated actionable task handoffs directly into Case Intelligence without creating a disconnected portal.

---

## 5. Verification Results

### Test Suite Summary
- **Phase 7 Dedicated Tests (`tests/test_phase7_cross_state_handoff.py`):** 10 / 10 passed (100%)
  1. `test_cross_state_handoff_request_and_metadata_persistence`: PASSED
  2. `test_destination_lea_scoped_case_and_evidence_visibility`: PASSED
  3. `test_metadata_only_evidence_scope_blocks_download`: PASSED
  4. `test_unrelated_jurisdiction_and_bank_isolation`: PASSED
  5. `test_full_state_machine_workflow`: PASSED
  6. `test_rejection_flow_and_access_revocation`: PASSED
  7. `test_cancellation_flow_and_access_revocation`: PASSED
  8. `test_deadline_expiration_and_escalation`: PASSED
  9. `test_idempotent_duplicate_actions_and_replays`: PASSED
  10. `test_concurrent_acceptance_conflict_protection`: PASSED

- **Full Pytest Suite:** 492 passed, 1 skipped (0 failures)
- **Mocha Blockchain Suites:**
  - `blockchain/gateway`: 14 / 14 passed
  - `blockchain/feature-engine`: 8 / 8 passed
  - `blockchain/chaincode/prediction-audit`: 7 / 7 passed
  - `blockchain/chaincode/geo-intelligence`: 9 / 9 passed
- **Frontend TypeScript & Vite Build:** Exit code 0 (0 compilation or bundling errors)
- **Model Integrity & Zero Drift Verification:** All 45 baseline SHA-256 model and dataset hashes remain 100% identical.

---

## 6. Changed Files

- `backend/app/models/models.py` (Added `CaseHandoff` model and relationships)
- `alembic/versions/0016_phase7_cross_state_handoff.py` (New Alembic migration)
- `backend/app/auth/rbac.py` (Active handoff geographic scope expansion and scope helpers)
- `backend/app/services/handoff_service.py` (New handoff business logic and state machine service)
- `backend/app/api/handoff_routes.py` (New REST endpoints for handoff lifecycle)
- `backend/app/api/evidence_routes.py` (Enforced handoff evidence scope restrictions)
- `backend/app/main.py` (Registered handoff router)
- `frontend/src/types/index.ts` (Added handoff TypeScript types)
- `frontend/src/services/api.ts` (Added handoff API client methods)
- `frontend/src/pages/CaseIntelligence.tsx` (Added Cross-Jurisdiction Assignments UI)
- `tests/test_phase7_cross_state_handoff.py` (New Phase 7 test suite)
- `tests/test_phase2_causal_predictions.py` (Timestamp microsecond precision in reversal test)

---

## 7. Pending External Gates & Disclosures

1. **Multi-Worker PostgreSQL Concurrency Gate:** Multi-worker distributed row locking tested in single-process SQLite test environment; production deployment with multiple Gunicorn/Uvicorn workers against PostgreSQL requires Postgres `FOR UPDATE NOWAIT` row locking validation.
2. **Visual Browser E2E Gate:** Automated browser recording / visual session validation pending live staging deployment.
3. **Delhi Model Geographic Scope Boundary:** Cross-state handoffs coordinate operational tasks across states (e.g. Mumbai, Karnataka); ML predictions remain calibrated strictly on Delhi geographic baseline data as documented in Phase 00 disclosures.

---

## 8. Rollback Procedure

If rollback of Phase 07 is required:
1. Run Alembic downgrade to Phase 06 head:
   ```bash
   alembic downgrade 0015_phase6_evidence_and_reports
   ```
2. Revert backend route registrations in `backend/app/main.py`.
3. Revert `backend/app/auth/rbac.py` to remove handoff scope expansion.
4. Revert `frontend/src/pages/CaseIntelligence.tsx` and `frontend/src/services/api.ts`.
5. Run test suite to verify clean Phase 06 baseline restoration.
