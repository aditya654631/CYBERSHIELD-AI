# Original problem statement → CyberShield traceability

Audit baseline: commit `90e792eba9f50e135367cf65c3a09658c61471df`, 17 September 2026 UTC.
Authority: the full problem statement pasted by the user in this conversation, not an inferred feature wishlist. No independent official SIH webpage was supplied or verified in this audit.

The statement asks for prediction of likely cash withdrawal locations using historical cybercrime/financial data; proactive state/local LEA interventions coordinated by I4C; intelligence for banks/FIs through CFCFRMS; and actionable sharing across jurisdictions. Its four deliverables are (a) predictive analytics with pattern detection, geospatial modelling and real-time alerts, (b) GIS risk dashboard with time/location/crime-category filters, (c) secure investigator access to alerts/intelligence reports/evidence documentation, and (d) notifications to LEAs, banks and I4C through SMS, email, API OR dashboard triggers.

Statuses: **TESTED-PROTOTYPE** means the bounded tested behaviour works, not production certification. **PARTIAL** means some required functionality exists. **GAP** means a missing capability in reviewed paths or a reproduced defect. **EXTERNAL** needs authorized access/pilot evidence. **UNVERIFIED** has not been demonstrated. Static absence searches are limited to the inspected repository.

| ID | PS phrase / intent | Actual evidence | Status / remaining work | Acceptance check |
|---|---|---|---|---|
| PS-01 | Centralized portal context | Complaint APIs and officer UI exist; no verified NCRP connector | PARTIAL / EXTERNAL: authorized ingestion contract, source identity, mapping and duplicate handling | Ingest a partner sandbox complaint once and preserve external reference |
| PS-02 | Approximately 8,000 complaints daily and growing | No national throughput/load benchmark run | UNVERIFIED: PS workload context, not today's verified statistic | Agree burst/concurrency/transaction-volume target and measure latency, errors and recovery |
| PS-03 | AI/ML-based system | XGBoost V7-compat location + V3 time model loaded in isolated E2E | TESTED-PROTOTYPE; preserve hashes and fallback disclosures | Real inference returns persisted ranked candidates and model version |
| PS-04 | Historical cybercrime and financial data | Synthetic Delhi training and qualification files; transaction feature pipeline | PARTIAL / EXTERNAL: authorized representative data and out-of-time evaluation | Report provenance, date split, leakage checks and real-case results |
| PS-05 | Predict potential withdrawal hotspots | Fresh case returns 3 locations; prediction and GIS overlay identity checked | TESTED-PROTOTYPE / EXTERNAL: real predictive usefulness unknown | Top-k recall, distance error and simple-baseline comparison on held-out real cases |
| PS-06 | Pattern detection | Transaction graph and ML features implemented | PARTIAL: synthetic/scenario provenance, incomplete live transaction feed | Verified transfers drive features; demo chain never claimed as observed movement |
| PS-07 | Geospatial risk modelling | Delhi clusters, coordinates and candidate generation | TESTED-PROTOTYPE within Delhi; broader regions unsupported | Region-level coverage and evaluation, explicit unsupported-region result |
| PS-08 | Real-time actionable intelligence | API predictions and WebSocket alerts; resolver uses transaction <= complaint.reported_at | GAP: incoming post-report transfers and event-driven refresh not demonstrated | New transfer after complaint produces versioned, time-causal updated prediction |
| PS-09 | Updated intelligence stays accurate | Persistence reuses old row if same top-1 and 3 locations, even changed score | GAP: service-level reproduction saved | Identical request reuses ID; changed results are not discarded merely because top-1 is unchanged |
| PS-10 | GIS-enabled dashboard | Case overlay, hotspot/ATM layers, active/historical distinction; frontend builds | TESTED-PROTOTYPE at API/build level; browser visual interaction unverified | Browser map loads, correct overlays and legends, no stale or wrong case |
| PS-11 | Real-time and potential risk zones | Latest unexpired case predictions separated from historical baselines | TESTED-PROTOTYPE: dedicated GIS module 14/14 passes alone; 5 fail in full suite | Fix shared test state and retain historical-vs-active semantics |
| PS-12 | Drill-down by location | District/risk filters and cluster drilldown | PARTIAL: regional scope and geographic naming need validation | Filter combinations match map/list/count and role scope |
| PS-13 | Drill-down by time | GET risk-map only district/risk_level; no time-range UI controls | GAP | Add explicit timestamp semantics, range validation and API/UI filtering |
| PS-14 | Drill-down by crime category | Fraud category displayed, no category query/control in reviewed map path | GAP | Category and combined filters affect clusters and counts consistently |
| PS-15 | Secure investigator interface | JWT/RBAC/jurisdiction code and dedicated security tests | TESTED-PROTOTYPE for tested checks; not security certification | Review all read/write/download routes; cross-role and object-level denial tests |
| PS-16 | Investigator access to alerts | Alerts API/UI, acknowledgement and action tracking | TESTED-PROTOTYPE; reliability under offline/restart not demonstrated | Relevant officer retrieves/acknowledges only authorized alert |
| PS-17 | Intelligence reports | Case intelligence and audit records | PARTIAL: complete shareable investigator report not found | Report includes source, timestamps, model, uncertainty, actions and references |
| PS-18 | Evidence documentation | Prediction snapshots and audit entries | PARTIAL: evidence attachments/custody workflow not found | Source, uploader, time, hash and authorized retrieval; no unsupported legal admissibility claim |
| PS-19 | Notifications via SMS/email/API OR dashboard | API + WebSocket dashboard trigger implementation; four mocked blockchain test suites pass separately | PARTIAL; SMS/email absence alone is NOT PS failure | Prove dashboard delivery, failure handling and acknowledgement; add provider only if chosen |
| PS-20 | Notify LEAs, banks and I4C | Stakeholder roles exist | PARTIAL: complete intended-recipient bank/jurisdiction routing unverified | Matrix of recipient roles, organizations and locations; no unrelated disclosure |
| PS-21 | Coordination across jurisdictions | Access isolation exists | GAP: controlled cross-state task handoff/acknowledgement not found | Origin case owner and destination team coordinate with scoped access |
| PS-22 | Deploy special teams / alert banks and ATMs | Alert escalation and action records | PARTIAL: dispatch assignment and external receipt not proven | Record assigned team, action, acknowledgement and outcome |
| PS-23 | Intelligence through CFCFRMS; faster fund blocking | Bank action lifecycle explicitly simulated; no verified partner connector | EXTERNAL | Authorized sandbox request + verified external acknowledgement; no fake completion |
| PS-24 | Increasing chances of recovery | No measured real financial intervention outcomes | EXTERNAL / UNVERIFIED | Separate confirmed hold, released hold and actual recovery; trace evidence |
| PS-25 | More effective proactive response | Saved synthetic metrics, alerts and graph | PARTIAL: warning-time/false-alert/response-time impact not proven | Shadow pilot, workload-aware baselines and operator outcome evaluation |

## Additional implementation choices (not literal PS mandates)

- **Top-3**, exact ATM prediction, a withdrawal **time model**, **LIME**, **blockchain**, PDF format, calibrated intervals, MFA and a particular queue vendor are not explicitly mandated by the supplied statement. Some are useful implementation choices; scope them by value and risk.
- Bank auto-freeze is not an autonomous authority granted by the PS. Bank intelligence and authorized action integration are the relevant goals.
- Mandatory time filtering on the map must not be confused with requiring an ML withdrawal-time model.
- No requirement specifies “90% accuracy.” Establish evaluation criteria instead of inventing an accuracy claim.
- All-India context does not validate this Delhi model nationally. A clearly scoped pilot is defensible, but must be disclosed.

## Evidence index (repository-relative)

- ML/scope/disclosures: `backend/app/services/prediction_service.py` (Delhi guard around 423; limitations around 665).
- Synthetic training: `ml/training/train_v7_compat.py`; saved results: `ml/evaluation/v7_compat_external_qualification.json`.
- Transaction cutoff: `backend/app/services/transaction_context_service.py` around 50.
- Stale result reuse: `backend/app/services/prediction_persistence_service.py` around 97–115; runtime reproduction in private audit folder.
- GIS filters: `backend/app/api/gis_routes.py` around 223; `frontend/src/pages/RiskMap.tsx` around 73.
- Access: `backend/app/auth/rbac.py`, `tests/test_phase1_security_authorization.py`.
- Alerts: `backend/app/api/alert_routes.py`, `backend/app/websocket/manager.py` (in-process connection list).
- Bank simulation: `backend/app/services/bank_action_service.py`.
- Explainability: `backend/app/services/prediction_explainability_service.py`.
- Full machine-readable test inventory: `TEST_FAILURES.csv`, `AUDIT_SUMMARY.json`; raw logs remain under ignored `scratch/`.
