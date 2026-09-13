# BLOCKCHAIN ACCESS CONTROL POLICY (RBAC & ABAC)

## 1. Consortium Membership Structure

The CyberShield consortium network defines 5 MSP organizational roles:

| Organization MSP | Role Category | Voting / Endorsement Weight |
| :--- | :--- | :--- |
| **Org1 (BankA)** | Commercial Financial Institution | Endorsement Peer (Financial Events) |
| **Org2 (BankB)** | Commercial Financial Institution | Endorsement Peer (Financial Events) |
| **Org3 (BankC)** | Commercial Financial Institution | Endorsement Peer (Financial Events) |
| **Org4 (I4C)** | Central Government Coordination | Admin / Regulatory Endorsement Peer |
| **Org5 (LEA)** | State Law Enforcement (Delhi Police) | Investigative Consumer / Field Endorsement Peer |

---

## 2. Function-Level Access Control Matrix

The chaincode (`GeoIntelligenceContract`) enforces Attribute-Based Access Control (ABAC) and MSP validation on every invoked method:

| Contract Function | Permitted MSPs | Required Client Role | Description |
| :--- | :--- | :--- | :--- |
| `SubmitSignal` | BankA, BankB, BankC, LEA | `client`, `service` | Publish verified ATM, branch, or field cash-out signal. |
| `GetSignal` | ALL (BankA–C, I4C, LEA) | `client`, `service`, `auditor` | Read single signal details by `event_id`. |
| `CorrectSignal` | Submitting MSP ONLY, I4C | `service`, `admin` | Amend previously submitted event metadata. |
| `RevokeSignal` | Submitting MSP ONLY, I4C | `admin` | Revoke a signal due to false-positive identification. |
| `QuerySignalsByCluster` | ALL (BankA–C, I4C, LEA) | `client`, `service` | Query active, non-revoked signals for a spatial cluster. |
| `AnchorPredictionHash` | I4C, LEA, CoreBackendMSP | `service` | Commit cryptographic SHA-256 hash of ML prediction. |
| `GetPredictionAnchor` | ALL | `client`, `service`, `auditor` | Retrieve anchored prediction hash for validation. |
| `VerifyPredictionAnchor` | ALL | `client`, `service`, `auditor` | Public cryptographic proof verification. |

---

## 3. Endorsement Policies

1. **Financial Signal Commits**:
   `AND('BankOrg.peer', OR('I4C.peer', 'LEA.peer'))`
   *Guarantees no individual bank can commit unverified activity without state/regulatory awareness.*

2. **Prediction Hash Commits**:
   `OR('I4C.peer', 'LEA.peer')`
   *Guarantees judicial anchoring authority remains strictly with authorized central agencies.*
