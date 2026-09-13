# PHASE B: HYPERLEDGER FABRIC IMPLEMENTATION PLAN

## Phase Overview

This implementation plan outlines the engineering milestones for Phase B, transitioning CyberShield AI from a centralized ML prediction prototype to a decentralized, multi-organization consortium intelligence platform.

---

## Milestone Breakdown

### Phase B.1: Consortium Network Scaffold
- Configure Fabric 2.5 LTS test network docker-compose architecture with 5 simulated organizations:
  - `Org1 (BankA)`, `Org2 (BankB)`, `Org3 (BankC)`, `Org4 (I4C)`, `Org5 (LEA)`.
- Configure Raft consensus orderer cluster (3 orderers).
- Generate crypto-materials (CAs, MSPs, mTLS certificates) using `cryptogen` / Fabric CA.
- Define consortium channel: `cybershield-intelligence-channel`.

### Phase B.2: Geo-Intelligence Smart Contracts (`GeoIntelligenceContract`)
- Implement Go / Node.js chaincode implementing:
  - `SubmitSignal`, `GetSignal`, `CorrectSignal`, `RevokeSignal`.
  - `QuerySignalsByCluster`, `AnchorPredictionHash`, `VerifyPredictionAnchor`.
- Implement ABAC access control checks enforcing MSP identity restrictions.
- Package and deploy chaincode via Fabric lifecycle (endorsement, commit).

### Phase B.3: Node.js Fabric Gateway Service
- Build lightweight Node.js Express microservice utilizing `@hyperledger/fabric-gateway`.
- Expose REST endpoints for FastAPI backend:
  - `POST /api/v1/gateway/signals`
  - `GET /api/v1/gateway/clusters/:clusterId/signals`
  - `POST /api/v1/gateway/predictions/anchor`
  - `GET /api/v1/gateway/predictions/:predictionId/verify`
  - `GET /api/v1/gateway/health`
- Implement mTLS identity delegation and connection pooling.

### Phase B.4: Blockchain Feature Engine
- Implement Python-side extractor in `backend/app/services/blockchain_feature_service.py`.
- Query cluster activity signals within causal time window (`event_timestamp <= prediction_reference_time`).
- Compute 17 engineered features defined in `blockchain_feature_contract.json`.
- Implement circuit breaker / fallback to defaults on gateway timeout.

### Phase B.5: Prediction Hash Anchoring & Verification
- Integrate asynchronous post-prediction anchoring in FastAPI:
  - Hash canonical prediction JSON via SHA-256.
  - Send anchor request to Gateway service asynchronously.
- Expose verification endpoint `GET /api/v1/predictions/{id}/blockchain-verify`.

### Phase B.6: Shadow Integration & Telemetry
- Execute secondary re-ranking model in **shadow mode** only.
- Record shadow predictions in telemetry table (`shadow_predictions`) without altering official Top-3.
- Monitor execution latency and feature availability metrics.

### Phase B.7: Fault-Tolerance & Security Audits
- Conduct network partition tests (kill orderer, kill gateway, drop peers).
- Validate fail-open behavior: verify core complaint registration and V4 predictions continue uninterrupted.
- Validate non-leakage invariant: ensure future-dated events are rejected by the Feature Engine.
- Validate privacy: ensure zero PII is written to ledger state.

### Phase B.8: End-to-End Multi-Bank Corroboration Golden Demo
- Execute multi-org demonstration:
  1. BankA reports ATM cash-out attempt in Cluster 12.
  2. BankB reports branch cash-out in Cluster 12.
  3. Feature engine calculates increased `distinct_verifying_banks` (2) and signal velocity.
  4. System registers complaint, generates official V4 prediction, anchors hash, and logs shadow rank.
  5. UI displays blockchain anchor verification status.

### Phase B.9: Promotion Review & Second-Stage Qualification
- Evaluate shadow ranker against frozen promotion criteria (MRR improvement, no Top-1 degradation, zero fallback failure).
- Hold formal governance review before considering production activation of second-stage ranker.
