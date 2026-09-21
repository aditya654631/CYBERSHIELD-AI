# Phase 0 measured baseline

Run date: **17 September 2026 UTC**. Report assembled/reviewed on 19 September; existing application commit unchanged: `90e792eba9f50e135367cf65c3a09658c61471df`. Results are not described as a new 19 September test run.

## Results actually executed

| Check | Result | Scope |
|---|---|---|
| `pytest tests -q -ra` | 321 passed, 74 failed, 1 skipped | Isolated SQLite; 396 collected cases, not proof of all features |
| TypeScript compile + Vite production build | Passed | No browser visual verification |
| Fabric gateway unit tests | 21 passed | Mocked dependencies |
| Blockchain feature engine | 13 passed | Local unit tests |
| Prediction audit chaincode | 10 passed | Local unit tests |
| Geo intelligence chaincode | 17 passed | Local unit tests |
| Fresh complaint manual E2E in test fixture | Passed | Complaint → model → stored Top-3 → GIS → alert → duplicate prevention |
| GIS module separately | 14 passed | Five GIS tests failed in full suite; cross-test state is implicated |
| Promoted and other artifact hashes | Unchanged | No retraining or model replacement |
| Git bundle verification and tracked ZIP CRC | Passed | Source/history preservation; not an operational restore drill |

Raw evidence: `scratch/phase0_20260917T175141Z/`. Earlier `phase0_20260917T175130Z` is an incomplete runner attempt; do not treat it as the authoritative run. A ZIP check originally ran before closing the writer; that audit-tool defect was corrected before the successful baseline run. Application code was not edited.

## Confirmed product defect

`prediction_persistence_service.py` treats matching model/mode and the same first-ranked cluster plus three stored locations as an identical prediction, even when the result fingerprint differs.

Reproduction: rank-2 input score changed from **0.0513000004** to **0.0563000004**, with rank-1 unchanged. Persistence returned **prediction ID 1 again**, with old rank-2 score **0.0513000004**. See `stale_prediction_reproduction.json` in the run directory. This is a service-level reproduction on synthetic fixture data, not a live bank observation. Fix in Phase 2 with meaningful identity/versioning tests.

## Failure analysis

All 74 failure node IDs/messages and one skip are in `TEST_FAILURES.csv`. They are not 74 independently established product defects.

- Several legacy ML tests reject the currently promoted V7-compat version by hard-coded older-version allowlists.
- Older GIS/dashboard tests expect HTTP 200 without supplying authentication; current protected endpoints return 401. Do not remove authentication to satisfy these tests.
- Shared session DB mutations and hard-coded IDs/counts produce collisions and cross-test effects: the modern GIS module passes all 14 checks alone.
- Legacy transaction/scenario and seed tests assume particular demo rows exist or own transactions. Their failures require fixture/contract review rather than blind model changes.
- A timestamp assertion expects a UTC offset string while the display is now explicitly IST. Resolve the actual API/display contract.
- A smaller combined rerun was also recorded in `targeted.xml/log`; it is diagnostic, not a replacement for the full-suite baseline. Some seed checks also fail without the larger suite's data side effects.
- The full run emitted 37,173 warnings. Triage underlying causes; do not hide all warnings globally.

## Backup coverage and limitations

- Repository bundle and tracked-file working snapshot saved; initial application checkout was clean. The only new working files are audit scripts/documents.
- All 7 discovered root/backend SQLite files copied through SQLite's backup API; integrity checks returned `ok`. One backend DB had zero tables, which is recorded rather than treated as meaningful production data.
- ML artifacts/evaluation files copied and SHA-256 hashes recorded.
- Local environment files copied only into private ignored backup storage; never publish these.
- Configured application database is **PostgreSQL**, not those SQLite files.
- A consistent **read-only PostgreSQL data snapshot** saved **17 tables / 98,259 rows**. Gzip records were reread to verify exported row counts. No operational writes were made by this snapshot.
- This snapshot is **not a full native restorable backup**: database roles, sequences, all DDL/objects and restore compatibility have not been validated. `pg_dump` was unavailable; Docker daemon was not running. Native dump + isolated restore drill remains an explicit Phase 0 prerequisite before destructive DB work.
- Keep `scratch/` private. It contains operational data and secret configuration. Backups on the same disk do not cover disk loss.

## PS alignment

Read `PS_TRACEABILITY.md`: 25 rows cover every substantive component of the supplied statement. Most implementation is a functioning **Delhi synthetic-data prototype**, not a verified national operational deployment.

Highest-priority gaps: time/category map filters; updated transaction cutoffs; stale-result reuse; reliable persistent notification delivery; investigator report/evidence workflow; controlled cross-state handoff; partner bank/CFCFRMS integration and real operational outcome evidence.

Separate optional choices: LIME, blockchain, exact ATM-level output, Top-3 count and calibrated ML timing intervals are not literal requirements of the supplied PS. Their existing claims still need to be accurate. The PS allows API/dashboard notification; absence of SMS/email alone is not noncompliance.

## ML and explanation observations

- Saved synthetic V7-compat combined report has Top-3 recall 32.66%; no real-world accuracy claim follows.
- `combined_6000` section versus reported component counts 1,395+2,000+2,000 requires denominator reconciliation.
- README's example 87% hybrid risk and 39-feature wording need reconciliation with runtime semantics/schema. Do not replace with invented headline accuracy.
- Fresh API probe produced a low-fidelity LIME label with mean R² about 0.5061. Current conservative classification considers individual fit/error, so mean alone need not determine the label. Investigate before declaring a display bug.
- Fresh response's timing uncertainty/basis fields were null even though an operational interval is present: audit whether provenance is lost between computation, persistence and response; do not claim this interval is calibrated.

## What this audit did not establish

No exhaustive defect guarantee, real-bank action, live NCRP/CFCFRMS connection, live Fabric proof, national load capacity, formal security certification, representative real-data model accuracy, or measured money recovery. Browser visual operation was not tested. `backend/tests` and miscellaneous standalone scripts outside the configured main suite were not comprehensively executed.

Phase 0 audit/handoff is available; full recovery readiness remains pending the native DB backup/restore gate. Later implementation prompts are in `docs/antigravity/`.
