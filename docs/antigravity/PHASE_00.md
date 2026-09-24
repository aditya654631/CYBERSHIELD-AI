# Phase 00: Baseline protection and measured audit

Dependencies: None.

PS mapping: PS-01–25: evidence baseline.

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

Read the existing audit scripts and recorded results first. If the application revision has not changed, retain the 17 September measured run with its date; rerun only checks needed by changes or unresolved concerns. Capture Git HEAD/status, all user changes, model hashes and environment versions. Preserve a Git bundle, actual working files (including relevant untracked work), model artifacts and safe configuration backup. Secret backups stay under ignored private storage, never in reports.
Use scripts/phase0_audit.py, phase0_case_probe.py and phase0_report.py for repeatable local evidence. Inspect them before running. Keep recorded command exit codes and logs. The original test suite had 321 pass / 74 fail / 1 skip; GIS alone 14 pass; 61 blockchain unit tests pass; frontend build and isolated fresh-case flow pass.
Complete the remaining backup gate: inspect the configured DB type without exposing credentials. Current PostgreSQL data-only snapshot is not pg_dump. Obtain compatible native backup tools or an approved provider backup mechanism, then restore into a NEW isolated database and verify schema/migrations/counts. Never restore over the live source. If infrastructure access is unavailable, record this gate as pending while completing audit work.
Classify all failures, inspect applicable API/UI paths and update every PS traceability row. No application fixes/retraining in this phase.

## Acceptance gate

Checkpoint restoration to a separate directory works; SQLite backups pass integrity checks; operational PostgreSQL has native backup + isolated restore evidence OR explicit pending status. Raw tests/build output and the complete failure list are retained. No claim of exhaustive defect discovery. Record browser QA separately from API/build evidence.
