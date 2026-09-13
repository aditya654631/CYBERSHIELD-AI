# BLOCKCHAIN INTELLIGENCE ARCHITECTURE — HYPERLEDGER FABRIC CONSORTIUM

## 1. Executive Summary & Purpose

The CyberShield AI Blockchain subsystem introduces a tamper-evident, privacy-preserving consortium ledger built on **Hyperledger Fabric**. It addresses the critical vulnerability in multi-bank cyber fraud investigations: **information silos and uncoordinated mule account cash-outs**.

By establishing a shared channel across banks, central intelligence (I4C), and law enforcement (LEA), the platform enables:
1. Multi-organization attestation of cash-out attempts and mule account movements.
2. Temporal intelligence extraction (e.g., recurrence velocity, distinct verifying banks).
3. Cryptographic integrity anchoring for production ML predictions to prove non-tampering during judicial proceedings.

---

## 2. Consortium Topology & Network Structure

```
                  ┌─────────────────────────────────────┐
                  │       Raft Ordering Service         │
                  │        (3 Orderer Nodes)            │
                  └──────────────────┬──────────────────┘
                                     │
           ┌─────────────────────────┼─────────────────────────┐
           │                         │                         │
     [ BankA Org ]             [ BankB Org ]             [ BankC Org ]
     - Peer0 (Endorser)        - Peer0 (Endorser)        - Peer0 (Endorser)
     - CA                      - CA                      - CA
           │                         │                         │
           └─────────────────────────┼─────────────────────────┘
                                     │
           ┌─────────────────────────┴─────────────────────────┐
           │                                                   │
      [ I4C Org ]                                         [ LEA Org ]
      - Peer0 (Endorser & Committer)                      - Peer0 (Committer)
      - CA                                                - CA
```

### Channel Design
- **Channel**: `cybershield-intelligence-channel`
- **Endorsement Policy**: Major events require endorsement by at least `OR(BankA, BankB, BankC)` plus `OR(I4C, LEA)` to guarantee cross-sector corroboration.

---

## 3. Core Functional Responsibilities

| Responsibility | Blockchain Role | Traditional Database (PostgreSQL) Role |
| :--- | :--- | :--- |
| **Ground-Truth Signals** | Verifiable, signed cash-out event proofs from banks/LEA. | Stores local complaint forms, victim details, FIR attachments. |
| **Prediction Integrity** | Anchors immutable SHA-256 hash of Top-3 predictions. | Serves active prediction queries to the frontend dashboard. |
| **Audit Trails** | Immutable historical log of signal submissions & revocations. | Application-level audit logs for UI user logins and button clicks. |
| **Cross-Bank Correlation** | Aggregates counts of distinct banks observing the same cluster. | Stores specific transaction hops for local visualization. |

---

## 4. Chaincode Modules: `GeoIntelligenceContract`

The smart contract executes the following deterministic transaction handlers:

1. `SubmitSignal(ctx, eventJSON)`: Validates organization identity via MSP, checks duplicate `event_id`, appends verified event to state.
2. `GetSignal(ctx, event_id)`: Fetches a single event record by unique ID.
3. `CorrectSignal(ctx, correctionJSON)`: Records a formal revision to an existing signal, maintaining full audit lineage.
4. `RevokeSignal(ctx, revocationJSON)`: Flags an existing signal as invalid/false-positive; downstream feature engines exclude revoked signals.
5. `QuerySignalsByCluster(ctx, cluster_id, start_time, end_time)`: Returns all valid signals associated with a spatial cluster within a bounded temporal window.
6. `AnchorPredictionHash(ctx, anchorJSON)`: Records the canonical SHA-256 hash of a generated ML prediction signed by the system.
7. `GetPredictionAnchor(ctx, prediction_id)`: Retrieves the anchored hash and submission metadata for tamper verification.
8. `VerifyPredictionAnchor(ctx, prediction_id, expected_hash)`: Compares the ledger state hash against the calculated database hash.

---

## 5. Architectural Non-Goals & Strict Boundaries

1. **NO Raw PII**: The ledger state will never store customer names, phone numbers, email addresses, or unhashed account identifiers.
2. **NO Primary Data Storage**: The ledger does not replace PostgreSQL for day-to-day CRUD operations.
3. **NO Blocking Dependency**: The frontend and core triage pipeline never block synchronously on blockchain network latency.
