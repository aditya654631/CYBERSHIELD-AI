# Phase 05: Durable alerts, delivery attempts and acknowledgement

Dependencies: 02,03,04.

PS mapping: PS-08, PS-16, PS-19, PS-20.

You are implementing one bounded phase in the existing CyberShield AI repository:
`C:\Users\adity\Downloads\CrimeTrace-AI-SIH-main\CyberShield AI`.

Read applicable AGENTS.md, `docs/phase0/AUDIT_REPORT.md`, `docs/phase0/PS_TRACEABILITY.md`, and the preceding phase handoff before editing. Inspect current code: paths below are starting points, not permission to overwrite newer work. Preserve user changes and working functionality. Reuse FastAPI/SQLAlchemy/Alembic and React/TypeScript; do not replace the stack or redesign unrelated screens.

The PS requires predictive withdrawal hotspots, patterns/geospatial modelling/real-time intelligence, GIS time/location/crime-category filtering, secure investigator alerts/reports/evidence, and notifications to police/banks/I4C via SMS/email/API OR dashboard. It also calls for coordination across jurisdictions and actionable financial intervention. LIME/blockchain/exact-ATM prediction are not mandatory PS technologies.

Implementation rules:
- Implement this phase end-to-end, not just a plan or scaffold. Use small additive changes with backwards compatibility where safe. Do not invent an external integration, training result, address, recovered amount or completed bank action.
- Before any schema change, inspect the current Alembic head and add a uniquely named revision (do not assume an old revision number). Test fresh upgrade and upgrade from current schema against disposable databases. Never migrate/reseed/delete operational data during verification. Destructive operational work requires separate user direction and a verified restore path.
- Test databases must be explicitly isolated before application imports. Do not weaken auth, remove meaningful tests, hide failures, lower fidelity thresholds or relabel synthetic data as real to obtain green output.
- Existing signed audit hashes and historical prediction snapshots must retain their original meaning. New versions append; don't rewrite historical facts.
- Keep UTC internally and explicit IST presentation; enforce current-user role and object access server-side. Do not trust role, owner, bank or jurisdiction supplied by the client. Never log credentials, tokens or full account data.
- Run targeted regression tests appropriate to the change and a frontend build when frontend changes. Run the full suite at the phase gate; compare remaining failures with the recorded baseline rather than pretending it is already green. Do not install arbitrary upgrades or retrain production models incidentally.
- If external access/data is absent, implement and test the local adapter/contract with a labelled fake, record the external acceptance checks as pending, and complete all independent work. No fake compliance or invented results.

Testing command pattern (PowerShell; disposable DB only):
```powershell
$env:ENVIRONMENT = 'test'
$env:DATABASE_URL = 'sqlite:///:memory:'
$env:AUTO_SEED_DEMO_DATA = 'false'
$env:FABRIC_GATEWAY_URL = 'http://127.0.0.1:1/api/v1'
.\.venv\Scripts\python.exe -m pytest tests -q -ra
```
Use the frontend's existing `npm run build` from its directory. PostgreSQL-specific constraints/concurrency require an isolated PostgreSQL integration run as well; SQLite alone cannot prove them.

Write a handoff to `docs/implementation/PHASE_XX_RESULT.md` using this phase's two-digit number. Include changed files, migrations, exact test commands/counts, before/after behaviour, PS IDs, evidence locations, pending external gates and rollback procedure. Do not proceed automatically into another phase. No Git push, PR publication, deployment or real SMS/bank messages are authorized by this prompt.

## Implement this phase

Inspect alert_service.py, alert_routes.py, websocket/manager.py, AlertsCenter.tsx and migrations. Add a persistent transactional outbox or equivalent minimal queue using existing infrastructure. Commit alert and outbound event consistently; don't rely solely on an in-memory WebSocket connection list.
Model recipient, channel, attempt, next retry, last error, delivery status, acknowledgement and escalation. Use bounded exponential backoff, worker leases/locking, idempotent processing and recovery after restart. Distinguish delivered from officer-acknowledged and resolved. Provide a worker command and explicit shutdown/recovery behaviour.
Recipient routing must reuse object/bank/jurisdiction authorization from Phase 3. Events must carry the relevant prediction version; supersede or expire stale alerts with history retained. Reconnect fetches missed authorized alerts through a persisted cursor/query; exactly-once external delivery cannot be promised.
Implement dashboard/API delivery first, with fake provider tests. SMS/email are optional channel adapters, not mandatory merely because the PS lists them. No real messages to people in development.

## Acceptance gate

Crash before/after dispatch, restart, disconnected recipient, duplicate queue processing, temporary/permanent provider error, expiry and acknowledgement tests pass. No lost durable event or unauthorized recipient. Operator can see queued/failed/delivered/acknowledged states; integration tests exercise actual worker processing, not just mocked enqueue calls.
