# Phase 02: Causal transaction updates and immutable prediction versions

Dependencies: 01.

PS mapping: PS-06, PS-08, PS-09.

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

Inspect transaction_context_service.py, ml_feature_service.py, prediction_service.py, prediction_persistence_service.py, prediction_contract.py, transaction_routes.py, prediction_routes.py, models.py and inference snapshots. Reproduce the saved stale-result bug before editing: same rank-1 with changed rank-2 score returns old ID/score.
Design a minimal authenticated transaction-ingestion/update contract. Store event time and first received/known time, external source/reference, verification/provenance and dedup key. Define corrections as traceable revisions. Historical backfill must not imply data was known earlier than ingestion; legacy unknown timestamps need explicit provenance.
Thread an explicit analysis_as_of through context/feature construction. Include only information available by that cutoff; future event-time rows must not leak in. Preserve the complaint-time mode for historical snapshots. Keep outcome/withdrawal labels out of prediction features.
Define input identity from canonical eligible transaction revisions, complaint inputs, model/schema versions and analysis semantics. Same request identity is idempotent; changed evidence must have a traceable new analysis snapshot even if top-1 is unchanged. Remove broad same-top1 reuse. Enforce concurrent idempotency at database level. Do not let a changing wall-clock timestamp create unlimited duplicates for unchanged retries.
Introduce new version links without rewriting old snapshots/audit anchors. Expose latest and history through compatible API/UI. New valid transfer triggers or queues recalculation; meaningful changed results update map and later alert orchestration. Refactor time-reference semantics explicitly when moving beyond complaint-time predictions; do not quietly re-anchor the old time model to now.

## Acceptance gate

Regression: same input gives same result ID; changed score/evidence with same top-1 is not dropped; post-report known transfer participates at a later cutoff; replay at earlier cutoff excludes it; duplicate ingest/concurrent retries do not double-count; future/late-arriving leakage tests pass; previous prediction/snapshot/hash remains unchanged. Tests cover authorized ingestion and invalid timestamps.
