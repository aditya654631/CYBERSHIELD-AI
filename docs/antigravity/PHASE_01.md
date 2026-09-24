# Phase 01: Stabilize tests and truthful product claims

Dependencies: 00.

PS mapping: PS-03–07, PS-15; reliability foundation.

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

Inspect tests/conftest.py and all failing test modules listed in docs/phase0/TEST_FAILURES.csv. Classify each failure as obsolete expected contract, authentication fixture, missing seed, cross-test state or application defect; preserve a rationale per node ID. The 14-test GIS module passes alone but had five failures in the full suite: reproduce ordering interference and isolate committed DB state per test or per appropriate fixture. Reset dependency overrides, globals and mutable caches reliably. Build explicit factory fixtures; avoid hidden reliance on test order, arbitrary fixed IDs or operational sample cases.
Replace hard-coded old model allowlists only after verifying the active artifact/schema manifest. Supply authenticated users for intended successful requests; keep independent 401/403 tests. Don't loosen production access. Reconcile IST human labels versus machine timestamp contracts.
Audit README.md, ModelPerformance.tsx, prediction display utilities and model verification API. Distinguish ranking scores, prioritization, synthetic evaluation and real validation. Resolve combined_6000 versus actual sample counts from evaluation code/data; derive the denominator, don't edit it by guess. Explain different experimental datasets instead of merging their metrics. Keep bank simulation labels and low-fidelity disclosures.
Do not silently replace the promoted model, widen operational scope or fix unrelated feature gaps.

## Acceptance gate

Affected tests pass independently and in the complete suite without order-dependent state. Every residual failure has a precise unresolved issue and reproduction, not a deleted test. Model artifact hashes unchanged. UI, README and evaluation metadata agree on provenance and denominators; no invented accuracy claims.
