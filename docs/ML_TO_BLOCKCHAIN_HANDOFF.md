# ML TO BLOCKCHAIN READINESS HANDOFF — PHASE A.4O-MASTER

## 1. System Context & Transition Overview

With the formal closure of the Machine Learning research track (Phase A.4A through Phase A.4O), CyberShield AI transitions from spatial model experimentation into **Phase B: Decentralized Consortium Intelligence** (Hyperledger Fabric).

The active ML baseline is formally frozen:
- **Location Model**: `cashout-location-xgb-v4` (SHA-256: `9ed5792ced4f8a6e79dc91e587e3c130d2fbadb5af6a73640397dc506dd9cdc9`)
- **Location Calibrator**: `location_calibrator_v4.joblib` (SHA-256: `65ceb736838d14cb865111aac6eddfad3838704ddf2fffc63a6b2bdd998a3664`)
- **Time Model**: `cashout-time-xgb-v3` (SHA-256: `41183f4579df70372102e98999967a5e63a9a2dad80f63668b45a5a66a2ed5e1`)
- **Feature Schema**: `feature_schema_v4.json` (43 location features, 20 time features; SHA-256: `572a1cadaea080c4ed013dcf07e2d1fca0720ba6c3d194bca7fc7d8e16d03c6e`)

All experimental challenger iterations (V5, V5.1, V5.2, V6, V6.1, V6.2, V6.3) failed pre-frozen learnability, anti-triviality, or shortcut-resistance gates and are archived as `NOT_PROMOTED`. Further model retraining is formally deferred until verified real-world ground truth (NCRP / Core Banking / LEA) becomes available.

---

## 2. Invariant Architectural Boundary

The integration of Blockchain (Hyperledger Fabric) must strictly adhere to the following 5 core tenets:

1. **Additive & Non-Disruptive**: Blockchain capabilities enrich the intelligence ecosystem without replacing or destabilizing the existing FastAPI / PostgreSQL runtime.
2. **Optional & Degraded-Safe**: If the Hyperledger Fabric network, orderer, or Node.js gateway is offline, the primary pipeline (complaint registration, V4 prediction, GIS mapping, alert dispatch) executes with zero downtime or user-facing errors.
3. **Shadow-First Integration**: All blockchain-derived features and secondary re-rankings run in shadow mode. Official production predictions, Case Intelligence views, and Law Enforcement Alerts remain 100% driven by V4 until formal Phase B promotion gates are met.
4. **Zero Raw PII / Financial Data on Ledger**: No victim names, phone numbers, raw account numbers, IFSC codes, or narrative complaint texts may be stored on the shared ledger. Only cryptographic hashes, opaque pseudonymized tokens, and macro spatial cluster IDs are permitted.
5. **No Synthetic / Arbitrary Score Blending**: No heuristic formulas (e.g. `0.8 * ML + 0.2 * Blockchain`) are permitted. Blockchain features will feed a distinct secondary ranker that must be rigorously trained and benchmarked against frozen criteria.

---

## 3. End-to-End Conceptual Dataflow

```
   [ Law Enforcement / Citizen Portal ]
                   │
                   ▼ (1. Register Complaint)
      ┌─────────────────────────┐
      │  FastAPI Core Backend   │ ──(Store)──► [ PostgreSQL ]
      │ (Complaint/Transaction) │              (Complaints, Accounts, Txns)
      └─────────────────────────┘
                   │
                   ▼ (2. Trigger Prediction)
      ┌─────────────────────────┐
      │  V4 Prediction Engine   │
      │  (Location V4, Time V3) │
      └─────────────────────────┘
                   │
       ┌───────────┴──────────────────────────────┐
       ▼                                          ▼
[ Official Production Output ]      [ Blockchain Readiness Flow ]
  - Top-3 Delhi Clusters (V4)         - Build Canonical Prediction Payload
  - Calibrated Probabilities          - Recompute Canonical SHA-256 Hash
  - Estimated Cash-out Window         - Query Fabric Gateway (Async / Shadow)
  - Prediction Mode: trained_ml                    │
       │                                           ▼
       ▼                               ┌───────────────────────────┐
[ PostgreSQL: Prediction / GIS ]       │ Hyperledger Fabric Anchor │
  - Persisted Top-3                    │ - Anchor Prediction Hash  │
  - Linked to Alert System             │ - Extract Cluster Events  │
  - Visualized on Risk Map             │ - Record Shadow Re-rank   │
                                       └───────────────────────────┘
```

---

## 4. Phase B Work Breakdown Structure

- **Phase B.1**: Fabric consortium network scaffold (5 orgs: BankA, BankB, BankC, I4C, LEA).
- **Phase B.2**: `GeoIntelligenceContract` chaincode deployment (signal submission, cluster aggregation, prediction hash anchoring).
- **Phase B.3**: FastAPI ↔ Node.js Fabric Gateway client interface.
- **Phase B.4**: Blockchain Feature Engine & time-safe temporal window extraction.
- **Phase B.5**: Prediction hash anchoring and audit verification endpoint.
- **Phase B.6**: Shadow re-ranking pipeline execution and telemetry logging.
- **Phase B.7**: Network partition, fault-tolerance, and security penetration testing.
- **Phase B.8**: Multi-organization corroboration end-to-end golden acceptance.
- **Phase B.9**: Second-stage ranker qualification and promotion review.
