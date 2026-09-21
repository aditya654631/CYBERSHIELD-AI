# Phase 10: Reproducible location-model evaluation and data readiness

Dependencies: 01,02,09.

PS mapping: PS-03–07, PS-25.

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

Inspect ml/training/train_v7_compat.py, ml/evaluation, candidate_generator.py, feature_pipeline.py and model_verification_service.py. Preserve production artifact hashes. Inventory dataset generator/version, actual rows and case counts, features, source provenance, target definitions and preprocessing. Reconcile the saved report denominator inconsistency programmatically.
Build a repeatable evaluation entry point for the same candidate universe and comparable information budget: current model, historical-hotspot baseline, distance baseline and appropriate random/reference baseline. Evaluate candidate recall separately from ranking recall so missing-target candidates are not hidden. Report Top-1/3/5, distance error, cohort counts and uncertainty estimates; don't call candidate-pair calibration proof of per-case real-world probability.
Use chronological and related-case/group separation appropriate to available data, ensuring derived historical features use only prior information. Keep train/tune/calibration/final test disjoint. For generated data, disclose generator-family dependence and test distribution changes rather than claiming a new random seed proves real-world generalization.
Implement authorized real-data import validation with provenance and schema checks, but do not fabricate that data. Set model promotion gates before comparing candidates; store experiments separately and promote only on documented evidence. Real data unavailable => real validation pending, not failed honesty.

## Acceptance gate

Same configuration/seed yields reproducible counts/metrics; no case-group leakage; baselines use comparable candidates; denominators match input records; separate real/synthetic reports. Existing model stays authoritative unless predeclared promotion evidence is met. Runtime preprocessing/artifact/schema parity tested.
