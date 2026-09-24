# Phase 04: Complete GIS filters and coherent case drilldowns

Dependencies: 02,03.

PS mapping: PS-10–14.

You are implementing one bounded phase in the existing CyberShield AI repository:
`<repository-root>`.

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

Inspect gis_routes.py, schemas.py, RiskMap.tsx, CashOutRiskMap.tsx and api.ts. Add explicit start/end and crime-category parameters end-to-end, keeping district/risk filtering compatible. Use a documented predicted-window overlap filter by default; if complaint-time filtering is offered, expose a distinct time_basis so the user knows which clock is filtered.
Validate ISO times, timezone conversion, reversed ranges and boundaries. Apply one consistent eligible, latest-version, unexpired-case and authorization predicate to map, case list, counts, amounts and drilldowns. Deduplicate complaints appearing in multiple candidate clusters. Crime type from case data, not historical label strings, should control active-case filtering.
Preserve historical baseline layers distinctly when filters return no active cases. Historical risk is not an active threat. Handle loading/error/empty states, filter reset and URL state. Do not label synthetic ATM inventory as verified live infrastructure.

## Acceptance gate

Tests exercise independent and combined filters, interval overlap, boundary dates/IST rollover, no match, expiry, latest-version selection, dedup totals and cross-role scope. API schema, frontend types and UI compile. Browser QA confirms filter persistence, legends and matching map/list/counts; document if browser QA unavailable.
