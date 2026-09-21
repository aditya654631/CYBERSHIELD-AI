# Phase 03: Server-side authorization and scoped sensitive access

Dependencies: 01,02.

PS mapping: PS-15, PS-20, PS-21.

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

Build a route/action/role/object matrix from every FastAPI router, including list/detail/graph/prediction/explanation/audit/bank actions and WebSocket. Inspect auth/rbac.py, security.py, websocket/manager.py and API dependencies. Reuse centralized checks; identify bank and jurisdiction through trusted organization IDs rather than text matching where feasible.
Define case owner, stakeholder visibility and least-privilege analyst/auditor policy without arbitrarily breaking existing approved access. Future handoff grants must be explicit and scoped, never broad state-wide disclosure by accident. Filter collection queries and verify direct object access, mutation permissions and WebSocket recipient access consistently.
Review token/session expiration, inactive accounts, rate limits and sensitive logging. Preserve public health behaviour without exposing diagnostics/secrets. Document production session/key configuration rather than fabricating security certification.
Add a minimal reusable authorization layer for future evidence downloads, reports, handoffs and bank callbacks. Do not treat a client-provided role or email as authority.

## Acceptance gate

Parameterized role/object tests include unauthenticated, expired/forged token, inactive user, cross-bank, cross-district/state, allowed national role and direct-ID access. Lists, GET details and websocket delivery agree on scope. Legitimate officers can complete existing workflows. No auth weakening to satisfy legacy tests.
