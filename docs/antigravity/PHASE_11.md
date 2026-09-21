# Phase 11: Honest timing uncertainty and stable LIME explanation

Dependencies: 02,10.

PS mapping: Optional timing/LIME quality supporting PS-17, PS-25.

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

Timing: inspect prediction_contract.py, time feature pipeline, time model target, persistence/response schemas and PredictionTiming.tsx. Preserve target reference semantics (current target measured from complaint reporting) unless a newly evaluated model explicitly changes it. Investigate null uncertainty/window_basis fields observed in the API despite an operational interval. Preserve uncertainty provenance end-to-end.
Evaluate errors on appropriate held-out observed withdrawals; missing outcomes are not zero-delay labels. If data supports intervals, separate calibration and test sets, report empirical coverage AND width by cohort and disclose distribution-shift limits. Otherwise keep heuristic operational windows visibly labelled; don't invent 90/95% coverage.
LIME: inspect exact official ranking/calibration wrapper, feature ordering/schema, persisted inference snapshot, background provenance and correlated/derived feature constraints. Ensure the explanation describes the same selected candidate score without changing ranking. Evaluate realistic perturbations, neighbourhood and sample-size choices on a predefined case set; repeat seeds to measure sign/rank stability and fidelity.
Current LOW_FIDELITY may reflect conservative worst-candidate/error logic even when mean R² is moderate. Inspect actual classifier and expose per-candidate diagnostics. Never lower thresholds solely to remove warnings. Keep explanations local/approximate and non-causal; alternate methods need their own validation.

## Acceptance gate

Historical time values/reference unchanged, current uncertainty/basis survives round-trip, interval coverage/width measured on untouched data OR heuristic label retained. Explanation uses correct immutable snapshot, ranking unchanged, cache invalidates on model/schema/snapshot changes; stability/fidelity report retained including bad cases. No guaranteed R² target invented.
