# CyberShield AI — Geo-Intelligence Chaincode (`geo-intelligence`)

## 1. Overview & Purpose

The `geo-intelligence` chaincode is a Hyperledger Fabric smart contract developed for the **CyberShield AI** consortium (SIH 26184). It provides a decentralized, auditable, and privacy-safe ledger for sharing and corroborating cyber cash-out intelligence across multiple financial institutions, law enforcement agencies (LEA), and national intelligence bodies (I4C).

> **Privacy & Compliance Statement**:
> The ledger stores **ONLY** privacy-safe, tokenized, and verified intelligence metadata (e.g. cluster IDs, districts, timestamps, verification confidence, opaque subject hashes). It **NEVER** stores raw customer PII, plain phone numbers, plain bank account numbers, UPI IDs, Aadhaar/PAN, or unhashed complaint text.

---

## 2. Consortium Organizations & MSPs

| Organization | Role | Actual MSP ID | Allowed Operations |
| :--- | :--- | :--- | :--- |
| **BankA** | Commercial Bank | `BankAMSP` | Submit cash-out/mule signals, query, correct own signals |
| **BankB** | Commercial Bank | `BankBMSP` | Submit cash-out/mule signals, query, correct own signals |
| **BankC** | Commercial Bank | `BankCMSP` | Submit cash-out/mule signals, query, correct own signals |
| **I4C** | Central Cyber Intel | `I4CMSP` | Submit signals, query, consortium-wide correction & revocation |
| **LEA** | Law Enforcement Agency | `LEAMSP` | Submit `LEA_CONFIRMED_CLUSTER`, query, correct own signals |

---

## 3. Supported Event Types

| Event Type | Submitting Orgs | Description |
| :--- | :--- | :--- |
| `ATM_WITHDRAWAL_CONFIRMED` | Banks, I4C | Confirmed cash-out withdrawal at ATM |
| `ATM_WITHDRAWAL_ATTEMPT` | Banks, I4C | Attempted/flagged ATM cash-out withdrawal |
| `BRANCH_CASHOUT_CONFIRMED` | Banks, I4C | Confirmed over-the-counter branch cash-out |
| `MULE_ACCOUNT_ACTIVITY` | Banks, I4C | Suspicious mule account velocity/activity |
| `LEA_CONFIRMED_CLUSTER` | LEA, I4C | Law enforcement confirmed geographic cash-out hotspot |
| `SIGNAL_CORRECTION` | Submitter Org, I4C | Immutable audit record correcting a previous signal |
| `SIGNAL_REVOKED` | Submitter Org, I4C | Immutable audit record revoking an invalid signal |

---

## 4. Signal Schema (`geo-intelligence-v1`)

```json
{
  "event_id": "EVT-BANKA-001",
  "event_type": "ATM_WITHDRAWAL_ATTEMPT",
  "organization_msp": "BankAMSP",
  "opaque_subject_ref": "opaque-sub-001",
  "cluster_id": 7,
  "district": "NEW_DELHI",
  "event_timestamp": "2026-09-13T10:15:00.000Z",
  "submitted_at": "2026-09-13T10:15:02.120Z",
  "verification_status": "VERIFIED",
  "confidence": 0.82,
  "source_reference_hash": "e3b0c44298fc1c149afbf4c8996fb92427ae41e4649b934ca495991b7852b855",
  "status": "ACTIVE",
  "created_tx_id": "8f3b29...",
  "created_by_msp": "BankAMSP",
  "corrected_by_event_id": null,
  "revoked_by_event_id": null,
  "schema_version": "geo-intelligence-v1"
}
```

---

## 5. Endorsement Policy

The chaincode operates under a consortium endorsement policy requiring signatures from at least 2 distinct member organizations:

```text
OutOf(2, 'BankAMSP.peer', 'BankBMSP.peer', 'BankCMSP.peer', 'I4CMSP.peer', 'LEAMSP.peer')
```

---

## 6. Contract Functions

### `InitLedger(ctx)`
Initializes the contract metadata on the channel.

### `SubmitSignal(ctx, signalJson)`
Submits a new verified signal. Enforces PII schema defense, MSP permission checks, field validations, and idempotency.

### `GetSignal(ctx, event_id)`
Fetches a single signal by its `event_id`.

### `SignalExists(ctx, event_id)`
Checks whether an `event_id` exists on the ledger.

### `GetCurrentSignalState(ctx, event_id)`
Returns current state summary including status (`ACTIVE`, `CORRECTED`, `REVOKED`).

### `CorrectSignal(ctx, target_event_id, correctionSignalJson)`
Marks the target signal as `CORRECTED`, records `corrected_by_event_id`, and creates a new immutable `SIGNAL_CORRECTION` ledger entry. Cross-bank modifications are strictly rejected unless authorized by `I4CMSP`.

### `RevokeSignal(ctx, target_event_id, revocationSignalJson)`
Marks the target signal as `REVOKED`, records `revoked_by_event_id`, and creates a new immutable `SIGNAL_REVOKED` ledger entry.

### `QuerySignalsByCluster(ctx, cluster_id, include_inactive)`
Queries signals associated with a specific cluster. Excludes non-active signals by default (`include_inactive=false`).

### `QuerySignalsByTimeWindow(ctx, start_time, end_time, include_inactive)`
Queries signals within an ISO-8601 time window based on `event_timestamp`.

### `QuerySignalsByOpaqueSubject(ctx, opaque_subject_ref, include_inactive)`
Queries all signals linked to an opaque subject identifier.

### `GetSignalHistory(ctx, event_id)`
Returns full immutable history of transactions and status transitions for a given signal.

---

## 7. Lifecycle Commands

### Package
```bash
peer lifecycle chaincode package geo-intelligence_1.0.tar.gz \
  --path blockchain/chaincode/geo-intelligence \
  --lang node \
  --label geo-intelligence_1.0
```

### Install (Run on each peer)
```bash
peer lifecycle chaincode install geo-intelligence_1.0.tar.gz
```

### Approve (Run on each org)
```bash
peer lifecycle chaincode approveformyorg \
  -o orderer.cybershield.net:7050 \
  --ordererTLSHostnameOverride orderer.cybershield.net \
  --tls --cafile <ORDERER_CA> \
  --channelID cyber-intelligence \
  --name geo-intelligence \
  --version 1.0 \
  --package-id <PACKAGE_ID> \
  --sequence 1 \
  --signature-policy "OutOf(2, 'BankAMSP.peer', 'BankBMSP.peer', 'BankCMSP.peer', 'I4CMSP.peer', 'LEAMSP.peer')"
```

### Commit
```bash
peer lifecycle chaincode commit \
  -o orderer.cybershield.net:7050 \
  --ordererTLSHostnameOverride orderer.cybershield.net \
  --tls --cafile <ORDERER_CA> \
  --channelID cyber-intelligence \
  --name geo-intelligence \
  --version 1.0 \
  --sequence 1 \
  --signature-policy "OutOf(2, 'BankAMSP.peer', 'BankBMSP.peer', 'BankCMSP.peer', 'I4CMSP.peer', 'LEAMSP.peer')" \
  --peerAddresses peer0.banka.cybershield.net:7051 --tlsRootCertFiles <BANKA_CA> \
  --peerAddresses peer0.bankb.cybershield.net:8051 --tlsRootCertFiles <BANKB_CA> \
  --peerAddresses peer0.bankc.cybershield.net:9051 --tlsRootCertFiles <BANKC_CA> \
  --peerAddresses peer0.i4c.cybershield.net:10051 --tlsRootCertFiles <I4C_CA> \
  --peerAddresses peer0.lea.cybershield.net:11051 --tlsRootCertFiles <LEA_CA>
```

---

## 8. Sample Invocation (SIMULATED DATA)

```bash
# BankA Submits Signal
peer chaincode invoke -o orderer.cybershield.net:7050 --tls --cafile <ORDERER_CA> \
  -C cyber-intelligence -n geo-intelligence \
  --peerAddresses peer0.banka.cybershield.net:7051 --tlsRootCertFiles <BANKA_CA> \
  --peerAddresses peer0.i4c.cybershield.net:10051 --tlsRootCertFiles <I4C_CA> \
  -c '{"function":"SubmitSignal","Args":["{\"event_id\":\"EVT-DEMO-001\",\"event_type\":\"ATM_WITHDRAWAL_ATTEMPT\",\"opaque_subject_ref\":\"opaque-demo-001\",\"cluster_id\":7,\"district\":\"NEW_DELHI\",\"event_timestamp\":\"2026-09-13T10:00:00.000Z\",\"confidence\":0.85}"]}'
```
