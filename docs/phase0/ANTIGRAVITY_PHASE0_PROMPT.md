# Paste this into Antigravity

Work in `<repository-root>`.

The user has authorized Phase 0: safe checkpoint, executable baseline audit and exact traceability against their cybercrime predictive analytics problem statement. Do not silently start a wholesale rewrite, retraining, destructive cleanup, reseeding of an operational DB, or later-phase feature work.

First read `docs/phase0/AUDIT_REPORT.md`, `PS_TRACEABILITY.md`, `AUDIT_SUMMARY.json` and `TEST_FAILURES.csv`. Read applicable AGENTS.md files. Preserve existing user changes. The recorded baseline commit is `90e792eba9f50e135367cf65c3a09658c61471df`.

Problem statement requirements: AI/ML analysis of historical cybercrime and financial data to predict likely cash-withdrawal hotspots; pattern detection, geospatial modelling, real-time alerts; GIS dashboard with time, location and crime-category drilldowns; secure investigator access to alerts, intelligence reports and evidence documentation; LEA/bank/I4C notifications via SMS, email, API OR dashboard; proactive interventions, CFCFRMS-related financial coordination and intelligence sharing across jurisdictions. Trace each requirement to PS-01 through PS-25. Do not invent a requirement for blockchain, LIME, exact ATM prediction, all notification channels, or 90% accuracy.

Current measured facts, which must be rechecked if code has changed:
- Main backend suite: 321 passed, 74 failed, 1 skipped. Do not call these 74 independent application defects.
- Frontend TypeScript and Vite builds passed.
- Gateway 21, feature-engine 13, prediction chaincode 10 and geo chaincode 17 tests passed; mocked unit tests are not live Fabric proof.
- Fresh isolated case → trained prediction → persisted Top-3 → GIS → alert/idempotency probe passed.
- GIS module alone: 14 passed, although 5 tests failed in the complete suite; investigate cross-test mutation.
- A changed rank-2 score with unchanged top-1 reused the old prediction ID and old score. This is a reproduced persistence issue, separate from missing live feeds.
- Model hashes unchanged.
- Configured DB is PostgreSQL. Seven local SQLite backups are not its backup. A read-only consistent PostgreSQL data snapshot covers 17 tables / 98,259 rows for this run, but native backup and restore validation remain pending. pg_dump was unavailable and Docker daemon was stopped.

Reproduction tools:
1. `.\.venv\Scripts\python.exe scripts\phase0_audit.py`
   It creates a NEW ignored `scratch/phase0_<UTC>` directory, Git bundle, tracked-file archive, local SQLite backups, model copies and logs. Tests use isolated SQLite, not operational PostgreSQL. A nonzero child-test exit is preserved in results.
2. `.\.venv\Scripts\python.exe scripts\phase0_case_probe.py <new-audit-directory>`
   Runs the existing manual E2E routine inside the test fixture and records demo snapshot plus stale-prediction reproduction. Log text from the legacy routine says “PRODUCTION”; this is actually isolated SQLite. Do not describe it as live production proof.
3. `.\.venv\Scripts\python.exe scripts\phase0_database_snapshot.py <new-audit-directory>`
   Optional authorized read-only configured PostgreSQL snapshot. It contains sensitive records; never publish/commit the private files. It is NOT a native restorable dump.
4. `.\.venv\Scripts\python.exe scripts\phase0_report.py <new-audit-directory>`
   Generates measured test summary and complete failure CSV. Do not rerun against unrelated evidence and retain old prose claiming new results.

Phase 0 remaining work:
- Obtain a compatible pg_dump/pg_restore or approved provider backup, preserve the configured database, and perform an isolated restore drill with schema/row-count checks. Never restore over the original DB.
- Group failures into outdated contracts, missing authentication fixtures, shared DB pollution, required seeded data, and real defects. Confirm selected failures separately. Never weaken security or delete assertions merely to make tests green.
- Review the current UI in a browser when available; existing evidence proves API flow and builds, not visual operation.
- Preserve an inventory of untested areas: live delivery, real bank/government integrations, real predictive quality, national load, real recovery outcomes and security review.

Required handoff:
1. Backup locations and precise restoration limitations.
2. One row per PS requirement: source phrase, code evidence, runtime evidence, status, gap and measurable acceptance check.
3. Exact test/build results and raw evidence locations.
4. Failure grouping without inflated bug counts.
5. Prioritized next-phase backlog, keeping Phase 0 blockers separate from new features.

Do not claim exhaustive defect discovery, 100% PS compliance, bank hold success, government integration or production readiness from these tests. Stop after producing a reviewable Phase 0 handoff; follow subsequent user authorization for fixes.
