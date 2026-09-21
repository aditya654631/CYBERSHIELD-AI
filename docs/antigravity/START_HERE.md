# CyberShield improvement roadmap

Yeh pack existing project ke actual source audit aur 17 September 2026 ke executed checks par based hai. 19 September ko application commit unchanged tha. Yeh prompts future implementation ke liye hain; new features abhi implement hone ka claim nahi hai.

## Kaise use karna hai

1. Antigravity mein same repository open karo.
2. Neeche Phase 00 se start karo; us file ka poora content paste karo. Existing audit evidence reuse/reconcile karna hai, bina reason sab tests repeat nahi karne.
3. Agent phase implement/verify kare aur `docs/implementation/PHASE_XX_RESULT.md` likhe.
4. Result, failed checks aur external blockers read karke next phase ka prompt do.
5. Saare prompts ek saath execute karne ko mat bolo. Combined file sirf convenient reference/copy source hai.

| Phase | Kaam | Prompt |
|---|---|---|
| 00 | Backup, audit, restore gate | [Open](PHASE_00.md) |
| 01 | Existing failing tests + truthful numbers/labels | [Open](PHASE_01.md) |
| 02 | New transfers + causal, versioned predictions + reproduced stale-result fix | [Open](PHASE_02.md) |
| 03 | Role/bank/jurisdiction access | [Open](PHASE_03.md) |
| 04 | Time/location/crime-category GIS filters | [Open](PHASE_04.md) |
| 05 | Durable alerts, retries, acknowledgements | [Open](PHASE_05.md) |
| 06 | Evidence documentation + investigator report | [Open](PHASE_06.md) |
| 07 | Controlled cross-state handoff | [Open](PHASE_07.md) |
| 08 | Bank adapter + truthful sandbox/live states | [Open](PHASE_08.md) |
| 09 | Verified outcomes + financial and response metrics | [Open](PHASE_09.md) |
| 10 | Synthetic/real-data readiness + baseline model evaluation | [Open](PHASE_10.md) |
| 11 | Timing uncertainty + LIME fidelity/stability | [Open](PHASE_11.md) |
| 12 | Configurable geography + second-region validation gate | [Open](PHASE_12.md) |
| 13 | Integrated workflow, load/recovery checks + real pilot readiness | [Open](PHASE_13.md) |

## Tumhari 12 gaps ki coverage

| Original gap | Phases |
|---|---|
| Synthetic-data model | 01, 10, 13 |
| Delhi-only coverage | 12 |
| Timing uncertainty | 02, 11 |
| Transaction updates | 02, 05 |
| Map filters | 04 |
| Secure access | 03; enforced again in 05–08 |
| Alert delivery | 05 |
| Simulated bank action | 08 |
| Evidence/reporting | 06 |
| Low LIME fidelity | 11 |
| Cross-state coordination | 07, 12 |
| Outcome measurement | 09, 13 |

Additional discovered work: baseline failures/obsolete fixtures (01), stale prediction reuse (02), full native PostgreSQL backup/restore (00), actual evaluated dataset count mismatch (01/10), uncertain timing metadata round-trip (11).

## External gates

Real bank/CFCFRMS APIs, representative authorized financial/cybercrime data, verified second-region geography, real outcomes and real operational deployment cannot be manufactured by coding. Relevant prompts complete local contracts/tests first and preserve external acceptance as pending. Geography config alone does not validate the model outside Delhi. API/dashboard alerts satisfy a permitted notification channel; SMS AND email are not both mandatory.

## Main evidence

- [Measured audit](../phase0/AUDIT_REPORT.md)
- [25-row PS mapping](../phase0/PS_TRACEABILITY.md)
- [Exact failures](../phase0/TEST_FAILURES.csv)
- [Machine summary](../phase0/AUDIT_SUMMARY.json)
- [All prompts in one file](ALL_PHASE_PROMPTS.md)

Audit tools: `scripts/phase0_audit.py`, `scripts/phase0_case_probe.py`, `scripts/phase0_database_snapshot.py`, `scripts/phase0_report.py`. Documentation pack generator: `scripts/generate_antigravity_plan.py`.

Private backups are in ignored `scratch/phase0_20260917T175141Z/`. Do not upload private configuration/database snapshot files into a prompt, repository or shared artifact.
