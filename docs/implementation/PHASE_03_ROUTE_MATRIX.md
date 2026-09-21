# Phase 03 route/action authorization matrix

This matrix records the server policy after Phase 03. `Scoped read` always means the
database user role and organization are authoritative; JWT role/email fields, request
body fields, display bank names, and frontend filtering do not grant access.

## Role scope

| Role | Read scope | Mutations |
|---|---|---|
| I4C_ADMIN | Nationwide | Platform/case intelligence actions allowed by route |
| STATE_LEA | Exact state, plus cases explicitly owned by the officer organization | Complaint/intelligence/alert actions allowed by route |
| DISTRICT_LEA | Exact state + district, plus cases explicitly owned by the officer organization | Complaint/intelligence/alert actions allowed by route |
| BANK_OFFICER | Complaints/accounts/actions carrying the same trusted `bank_organization_id` | Relevant alert acknowledgement/escalation and own bank-action transition only |
| ANALYST | I4C analyst: national; LEA analyst: organization geography | Existing analytical actions explicitly listed below; no complaint creation, correction/reversal, alert acknowledgement, bank transition, or audit-log access |
| AUDITOR | I4C auditor: national read; LEA auditor: organization geography | Read-only; audit logs are national only for I4C audit organizations and otherwise limited to the auditor organization |

Missing or incompatible role/organization configuration is denied. Out-of-scope direct
objects return `404`; role-denied actions return `403`. Historical rows are not assigned
invented owners or bank stakeholders. Phase 07 must add explicit handoff grants rather
than expanding geographic access.

## HTTP and WebSocket matrix

| Route/action | Authentication | Object/collection rule | Mutation roles |
|---|---|---|---|
| `GET /health` | Public | Sanitized service readiness only | Read-only |
| `POST /api/v1/auth/login` | Public credentials | Active user and valid database role/organization pairing | Session issue only |
| `GET /api/v1/auth/me` | JWT | Current active database user | Read-only |
| `GET /api/v1/complaints` | JWT | Scoped complaint collection | Read-only |
| `POST /api/v1/complaints` | JWT | Server binds owner user/org and LEA jurisdiction | I4C_ADMIN, STATE_LEA, DISTRICT_LEA |
| `GET /api/v1/complaints/{id}` | JWT | Scoped complaint; otherwise 404 | Read-only |
| `GET /api/v1/complaints/{id}/graph` | JWT | Same complaint object check | Read-only |
| `GET /api/v1/complaints/{id}/transactions[/context]` | JWT | Same complaint object check | Read-only |
| `POST /api/v1/complaints/{id}/transactions` | JWT | Same complaint object check; server actor/time | I4C_ADMIN, STATE_LEA, DISTRICT_LEA, ANALYST |
| `POST .../transactions/correction` and `/reversal` | JWT | Same complaint object check; immutable correction chain | I4C_ADMIN, STATE_LEA, DISTRICT_LEA |
| `POST .../transactions/{tx}/retry-analysis` | JWT | Same complaint + transaction check | I4C_ADMIN, STATE_LEA, DISTRICT_LEA, ANALYST |
| `GET /api/v1/predictions/{complaint}` and `/versions` | JWT | Same complaint object check | Read-only |
| `GET /api/v1/predictions/version/{prediction}` | JWT | Parent complaint object check | Read-only |
| `GET /api/v1/predictions/{prediction}/explanation` | JWT | Parent complaint object check | Read-only |
| `GET /api/v1/predictions/{prediction}/audit-verification` | JWT | Parent complaint object check | Read-only |
| `POST /api/v1/predictions/{complaint}` | JWT | Same complaint object check | I4C_ADMIN, STATE_LEA, DISTRICT_LEA, ANALYST |
| `GET /api/v1/risk-map`, `/clusters` | JWT | Geographic scope; bank users receive clusters linked to bank-scoped complaints | Read-only |
| `GET /api/v1/clusters/{id}` | JWT | Same GIS scope; otherwise 404 | Read-only |
| `GET /api/v1/risk-map/prediction/{complaint}` | JWT | Same complaint object check | Read-only |
| `GET /api/v1/alerts`, `/alerts/{id}` | JWT | Scoped parent complaint | Read-only |
| `POST /api/v1/alerts/prediction/{id}`, `/generate/{complaint}` | JWT | Scoped parent complaint | I4C_ADMIN, STATE_LEA, DISTRICT_LEA, ANALYST |
| `POST /api/v1/alerts/{id}/acknowledge` | JWT | Scoped parent complaint/bank stakeholder | I4C_ADMIN, STATE_LEA, DISTRICT_LEA, BANK_OFFICER |
| `POST /api/v1/alerts/{id}/escalate` | JWT | Scoped parent complaint/bank stakeholder | I4C_ADMIN, STATE_LEA, DISTRICT_LEA, BANK_OFFICER |
| `GET /api/v1/bank-actions`, `/{id}` | JWT | LEA scope or exact `bank_organization_id` | Read-only |
| `POST /api/v1/bank-actions/{id}/transition` | JWT | Exact bank organization for BANK_OFFICER; national for I4C_ADMIN | BANK_OFFICER, I4C_ADMIN |
| `GET /api/v1/dashboard/summary` | JWT | All complaint/prediction/alert aggregates use the same scoped complaint IDs | Read-only |
| `GET /api/v1/analytics/*` | JWT | Same scoped dashboard data; timeline contains no account identifiers | Read-only |
| `GET /api/v1/model/performance` | JWT | Model-level synthetic evaluation metadata; no case rows | Read-only |
| `GET /api/v1/audit[/logs]` | JWT | I4C audit org: national; other auditor org: its users only | I4C_ADMIN, AUDITOR; read-only |
| `GET /api/v1/system/status` | JWT | Operational diagnostics | I4C_ADMIN, ANALYST, AUDITOR |
| `WS /ws/alerts` | Active JWT | I4C admin; matching state/district; exact bank organization; role allowlist per event | Server-to-client event delivery |

## Reusable policy entry points

- `filter_complaints_by_jurisdiction`: collection scope.
- `verify_complaint_access`: complaint and child-object direct access.
- `verify_alert_access`: alert parent-case access.
- `verify_bank_action_access`: exact bank action or LEA/I4C case access.
- `complaint_bank_organization_ids`: WebSocket and future notification recipients.
- `resolve_bank_organization_id`: one-time unique mapping against the trusted organization registry; authorization never performs bank-name substring matching.

Future evidence downloads, reports, callbacks, and handoffs must call these policy entry
points or a narrower policy built on the same trusted IDs.
