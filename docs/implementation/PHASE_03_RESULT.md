# Phase 03 Handoff: Server-side authorization and scoped sensitive access

**Phase:** 03  
**Problem-statement mapping:** PS-15, PS-20, PS-21  
**Dependencies:** Phases 01 and 02  
**Baseline commit:** `90e792eba9f50e135367cf65c3a09658c61471df`  
**Execution date:** 20 September 2026  
**Status:** Completed for the local application and isolated SQLite acceptance gate. Phase 04 has not started.

## Outcome

CyberShield now applies one server-side object scope to complaint lists, direct records,
child records, GIS data, dashboard aggregates, analytics, alerts, bank actions, audit
logs, and WebSocket delivery. The logged-in database user and trusted organization IDs
are authoritative. A JWT role claim, request-body actor, bank display name, frontend
filter, or guessed object ID cannot expand access.

The complete reviewed route/action/role/object policy is recorded in
`docs/implementation/PHASE_03_ROUTE_MATRIX.md`.

## Before and after

| Area | Before Phase 03 | After Phase 03 |
|---|---|---|
| Geographic access | Several endpoints performed their own partial state/district checks. Aggregates and direct IDs could disagree. | Collection and direct-object access reuse centralized complaint scope. State and district boundaries are enforced consistently. |
| Bank access | Some checks depended on bank-name text matching. | Bank visibility and bank-action mutation use exact trusted `organization.id` foreign keys. |
| Ownership | Complaint ownership was implicit or inferred. | New complaints bind `owner_user_id` and `owner_organization_id` from the authenticated server context. |
| Analyst/auditor | Read and mutation boundaries varied by route. | Analysts receive their configured I4C or LEA scope; auditors are read-only and audit records are organization-scoped unless the auditor belongs to I4C. |
| Dashboard/analytics | Some totals and timelines could be calculated independently of complaint scope; analytics included hard-coded demo values. | Counts, distributions, recent records, and timelines derive from the same authorized complaint set and persisted data. |
| GIS | Cluster collection and detail access were not uniformly object-scoped. | Geographic users receive their jurisdiction; bank users receive only clusters linked to their bank-scoped complaints. |
| WebSocket alerts | A broad/default role and incomplete recipient context could deliver events outside HTTP scope. | Connections carry database role/org scope and each event specifies permitted roles, geography, and exact bank organization recipients. Unknown/default roles receive nothing. |
| Session validation | Signature and active-user checks existed, but incompatible role/organization pairs could still be represented. | Expired/forged tokens, inactive users, and invalid role/organization pairings are rejected. JWT role text does not override the database role. |
| Enumeration | A duplicate transaction conflict could reveal a reference belonging to another case. | Cross-case duplicate references return a generic conflict unless the caller can access the referenced case. Out-of-scope direct objects return 404. |

## Implementation

### Trusted scope data and migration

Alembic revision `0013_phase3_authorization_scope_ids` is the single current head. It
adds nullable, indexed foreign keys:

- `complaints.owner_organization_id`
- `complaints.owner_user_id`
- `accounts.bank_organization_id`
- `bank_actions.bank_organization_id`

The migration deliberately leaves historical values `NULL`; it does not invent owners
or bank provenance. Newly created records are bound from authenticated context or a
unique match in the trusted organization registry.

### Central policy

`backend/app/auth/rbac.py` now provides reusable checks for complaint collections,
complaint objects, alerts, bank actions, bank stakeholders, national scope, and trusted
bank organization resolution. `backend/app/auth/security.py` validates active users and
compatible role/organization types for HTTP and WebSocket sessions.

The same policy is consumed by complaint, transaction, prediction, GIS, alert,
bank-action, dashboard, analytics, audit, and system-status paths. It is also the base
for future evidence downloads, reports, callbacks, and explicit cross-state handoffs.

### Sensitive delivery and diagnostics

WebSocket delivery now requires an explicit event role allowlist plus matching
jurisdiction or organization. Alert acknowledgements no longer permit the read-only
auditor role. `/health` remains public; `/api/v1/system/status` requires an authorized
operational role. No credentials, tokens, or full account data were added to logs.

## Phase-specific files

| File | Phase 03 purpose |
|---|---|
| `alembic/versions/0013_phase3_authorization_scope_ids.py` | Adds trusted owner/bank organization keys without fabricating legacy provenance. |
| `backend/app/models/models.py` | Defines new foreign keys and organization relationships. |
| `backend/app/auth/rbac.py` | Central collection and direct-object authorization policy. |
| `backend/app/auth/security.py` | Active-session and role/organization validation for HTTP and WebSocket. |
| `backend/app/api/auth_routes.py` | Refuses login for an incompatible role/organization pairing. |
| `backend/app/api/complaint_routes.py` | Server-owned case attribution, trusted bank mapping, and generic duplicate conflicts. |
| `backend/app/api/transaction_routes.py` | Trusted bank mapping for ingested transaction accounts. |
| `backend/app/api/bank_action_routes.py` | Exact organization-based collection, detail, and transition authorization. |
| `backend/app/api/alert_routes.py` | Scoped queries, exact WebSocket recipients, and least-privilege acknowledgement. |
| `backend/app/api/gis_routes.py` | Applies geographic/bank scope to GIS lists and direct cluster reads. |
| `backend/app/api/analytics_routes.py` | Replaces hard-coded demo analytics with scoped persisted results. |
| `backend/app/api/audit_routes.py` | Limits non-I4C auditors to their own organization. |
| `backend/app/api/system_routes.py` | Protects operational system telemetry. |
| `backend/app/services/dashboard_service.py` | Uses one authorized complaint set for all aggregate calculations. |
| `backend/app/services/bank_action_service.py` | Persists exact stakeholder bank organization on new actions. |
| `backend/app/websocket/manager.py` | Enforces role, organization, state, and district recipient scope. |
| `database/seed/seed_data.py` | Associates the known SBI demo account with its trusted bank organization. |
| `tests/conftest.py` | Adds explicit LEA and bank organization fixtures. |
| `tests/test_phase3_authorization_matrix.py` | Parameterized HTTP, object, WebSocket, and migration acceptance coverage. |
| `docs/implementation/PHASE_03_ROUTE_MATRIX.md` | Records the reviewed route/action/role/object contract. |

Existing regression tests were adjusted only where they previously depended on an
unscoped user, ambiguous organization, non-unique global transaction reference, or an
auditor mutation that conflicts with the documented read-only policy.

## Verification evidence

All application tests used an explicitly isolated database before importing the app.
No operational database was migrated, reseeded, or deleted.

| Gate | Command / evidence | Result |
|---|---|---|
| Full backend suite | `python -m pytest tests -q -ra --junitxml=scratch/phase3_20260920T141500Z/pytest.xml` with test environment and isolated SQLite configured | **456 passed, 1 skipped, 0 failed** in 73.81s. The skip is the pre-existing opt-in live-infrastructure test. |
| Authorization + existing auth/WS/migration regression gate | `pytest tests/test_phase3_authorization_matrix.py tests/test_phase1_security_authorization.py tests/test_websocket_reliability.py tests/test_database_migrations_phase2.py -q` | **69 passed**. |
| Final alert/authorization regression after query cleanup | `pytest tests/test_step12_prediction_alert_integration.py tests/test_phase3_authorization_matrix.py -q` | **45 passed**. |
| Python syntax/import compilation | `python -m compileall backend alembic` | Passed. |
| Alembic graph | `python -m alembic heads` | One head: `0013_phase3_authorization_scope_ids`. |
| Frontend production build | `npm run build` in `frontend` | Passed: TypeScript and Vite completed with zero errors in 7.62s. |
| Model/data integrity | SHA-256 comparison against `scratch/phase0_20260917T175141Z/baseline.json` | **45/45 matched**, 0 altered, 0 retrained. |

Evidence files:

- `scratch/phase3_20260920T141500Z/pytest.xml`
- `scratch/phase3_20260920T141500Z/pytest.log`
- `scratch/phase3_20260920T141500Z/frontend-build.log`
- `scratch/phase3_20260920T141500Z/artifact_verification.json`

The suite reports deprecation warnings, primarily use of naive `datetime.utcnow()` and
older SQLAlchemy/Alembic APIs. They did not fail this gate and remain technical debt;
they have not been hidden or reclassified as successes.

## Pending gates and limits

- **Native PostgreSQL migration and multi-worker authorization/concurrency run:**
  PENDING. SQLite proves the local schema and policy behavior but cannot prove native
  PostgreSQL constraints, connection-pool behavior, or deployment configuration.
- **Historical trusted-scope mapping:** PENDING operational data-governance work.
  Historical rows remain `NULL` until an authorized source establishes their owner or
  stakeholder organization. Bank users will not gain visibility from an unverified
  bank-name guess.
- **Cross-state handoff grants:** PENDING Phase 07. This phase intentionally does not
  create broad cross-state visibility.
- **Real bank/CFCFRMS callback identity:** PENDING external integration. Exact local
  bank organization scope does not prove a partner bank's production identity.
- **Distributed rate limiting and immediate token revocation:** PENDING deployment
  design. The current limiter is process-local, and `X-Forwarded-For` is trustworthy
  only when a controlled reverse proxy strips and sets it. JWTs expire and inactive
  users are rejected on each authenticated request, but there is no distributed token
  denylist.
- **Browser visual and accessibility QA:** PENDING. The production bundle builds, but
  no browser-based visual or keyboard/accessibility pass was claimed.
- **Independent penetration test/security certification:** PENDING external review.
  Passing authorization tests is engineering evidence, not a certification.

## Rollback

1. Preserve a database backup and verify its restore path before touching any deployed
   database.
2. On an isolated compatible database, run `python -m alembic downgrade
   0012_transaction_created_by_user_id` to remove the four Phase 03 indexes, foreign
   keys, and nullable columns.
3. Revert the Phase 03 application and test files listed above together so application
   models do not reference removed columns.
4. Re-run the Phase 02 backend gate and frontend build against an isolated database.

Rollback was documented but not executed against operational data. No Git push, pull
request, deployment, model retraining, real notification, or real bank action occurred.

