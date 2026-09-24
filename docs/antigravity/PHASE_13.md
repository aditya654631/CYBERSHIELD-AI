# Phase 13: Integrated pilot readiness and final PS acceptance

Dependencies: 00–12 local gates; external gates explicitly tracked.

PS mapping: PS-01–25.

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

Review all phase handoffs and regenerate a source/evidence/acceptance matrix for every PS row. Run a fresh end-to-end test with late transfer, versioned prediction, filtered map, authorized alert/acknowledgement, scoped handoff, fake-bank confirmed response, evidence report and outcome record. Exercise failure/restart paths, not only the happy path.
Run a production-like isolated PostgreSQL stack with migrations, backup/restore and worker recovery. Establish load targets from complaint bursts, transfers per case, repeated inference and users; 8,000/day alone is not a sufficient benchmark. Measure p50/p95/p99, errors, queue delay and resources under documented hardware/data/model settings; set acceptance budgets before the test.
Perform browser workflow checks for each intended role. Keep live external provider tests separate and authorized. Review sensitive logs, deployment config, health/readiness and operational runbooks; no self-issued security certification.
Prepare an authorized real-data shadow pilot: record predictions prospectively, compare simple baselines, track warning time/false-alert workload/verified financial outcomes and drift. Do not allow autonomous punitive action based solely on location risk.
Produce a release checklist with working prototype, sandbox-verified, externally validated and pending items. Do not deploy or send real notifications/financial actions as part of this prompt.

## Acceptance gate

Every PS requirement has current evidence and an honest status. All release-blocking regressions resolved; no undisclosed failing suite. Recovery/load/browser results reproducible. External unknowns have concrete partner/data requirements. Pilot go/no-go is based on measured criteria, not a manufactured completion percentage.
