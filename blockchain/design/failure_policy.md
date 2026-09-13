# BLOCKCHAIN FAULT-TOLERANCE & FAILURE POLICY

## 1. Core Principle: Fail-Open Architecture

The Hyperledger Fabric consortium layer is an **additive enrichment and integrity subsystem**. Under no circumstances may an outage, latency spike, or network partition within the blockchain infrastructure degrade or block core citizen complaints, law enforcement investigations, or baseline ML predictions.

---

## 2. Failure Scenarios & System Responses

| Failure Mode | Root Cause | System Response | Impact on Production ML |
| :--- | :--- | :--- | :--- |
| **Fabric Gateway Offline** | Node.js Gateway service crashed or port unreachable. | FastAPI catches connection timeout; logs warning; skips blockchain feature retrieval; continues with standard V4 prediction. | **ZERO IMPACT**: V4 prediction completes normally; prediction mode remains `trained_ml`. |
| **Peer / Orderer Outage** | Insufficient peers for Raft consensus or endorsement policy. | Prediction hash anchoring queue marks transaction as `PENDING_RETRY`; background worker attempts deferred commit. | **ZERO IMPACT**: Production prediction persists immediately to PostgreSQL; Case Intelligence loads without delay. |
| **Feature Extraction Timeout** | Distributed ledger query exceeds latency budget (> 500ms). | Blockchain Feature Engine aborts query; returns zero-initialized default features (`default_value: 0`). | **ZERO IMPACT**: Secondary shadow ranker receives defaults; official V4 ranking unaffected. |
| **Hash Verification Failure** | DB record altered or blockchain anchor tampered with. | Verification endpoint returns status `MISMATCH` with tamper alert flag. | **ALERT RAISED**: UI highlights discrepancy for human forensic auditor; DB record is NOT deleted or rolled back. |
| **Network Partition (Split-Brain)** | Network disconnects Bank peers from LEA peers. | Peers reject new endorsements until quorum restored; existing ledger history remains read-only available. | **ZERO IMPACT**: Production FastAPI backend operates fully autonomously on local PostgreSQL database. |

---

## 3. Resilience Guarantees

1. **Complaint Persistence Isolation**: Complaints are written to PostgreSQL before any blockchain call is triggered. Blockchain failure can never roll back or abort a registered complaint.
2. **Prediction Idempotency Preserved**: If an async anchoring task retries, it uses `prediction_id` as the unique ledger idempotency key to prevent duplicate ledger transactions.
3. **Graceful UI Degradation**: In the frontend, if the blockchain gateway is unreachable, the "Ledger Verification" badge displays `BLOCKCHAIN_OFFLINE (UNVERIFIED)` without breaking map rendering or case intelligence views.
