# CyberShield AI — Fabric Gateway Service (Phase B.3)

> **CRITICAL ARCHITECTURE NOTICE:**
> **SIMULATED CONSORTIUM — NO LIVE BANK CONNECTIVITY**
> All financial entities (BankA, BankB, BankC) and institutional participants (I4C, LEA) run as localized cryptographic participants under Hyperledger Fabric v2.5.9 on the `cyber-intelligence` channel. No live banking APIs or external accounts are accessed.

---

## 1. Overview & Architecture

The Fabric Gateway service provides application-level access to the `geo-intelligence` chaincode using the official `@hyperledger/fabric-gateway` and `@grpc/grpc-js` SDK.

Application callers interact via high-level service interfaces rather than raw CLI invocations (`peer chaincode invoke` / `query`).

```
  +-------------------------------------------------------------+
  |              CyberShield Gateway Service                    |
  |                                                             |
  |  +------------------+             +----------------------+  |
  |  | Express HTTP API |             | Multi-Org Simulation |  |
  |  | (/api/v1/...)    |             | (BankA/B/LEA/I4C)    |  |
  |  +--------+---------+             +----------+-----------+  |
  |           |                                  |              |
  |           v                                  v              |
  |    +-----------------------------------------------+        |
  |    |         GeoIntelligenceService Layer          |        |
  |    +-----------------------+-----------------------+        |
  |                            |                                |
  |                            v                                |
  |    +-----------------------------------------------+        |
  |    |        Fabric Gateway Contract Client         |        |
  |    |    (evaluateTransaction / submitTransaction)  |        |
  |    +-----------------------+-----------------------+        |
  |                            | (gRPC + Mutual/Server TLS)     |
  +----------------------------|--------------------------------+
                               v
      +--------------------------------------------------+
      |  Hyperledger Fabric 2.5.9 Network                |
      |  - Channel: cyber-intelligence                   |
      |  - Chaincode: geo-intelligence (v1.0)            |
      |  - Orgs: BankA, BankB, BankC, I4C, LEA (5 Peers) |
      +--------------------------------------------------+
```

---

## 2. Crypto Material & Org Mapping

All cryptographic credentials adhere directly to the B.1 generated MSP layout:

| Organization | MSP ID | Peer Endpoint | Host Alias | Identity Role |
|---|---|---|---|---|
| **BankA** | `BankAMSP` | `localhost:7051` | `peer0.banka.cybershield.net` | Submitter (Cash-out & Mule signals) |
| **BankB** | `BankBMSP` | `localhost:8051` | `peer0.bankb.cybershield.net` | Submitter (Cash-out & Mule signals) |
| **BankC** | `BankCMSP` | `localhost:9051` | `peer0.bankc.cybershield.net` | Consortium Participant (Read/Corroborate) |
| **I4C** | `I4CMSP` | `localhost:10051` | `peer0.i4c.cybershield.net` | Central Intelligence Consumer / Admin |
| **LEA** | `LEAMSP` | `localhost:11051` | `peer0.lea.cybershield.net` | Law Enforcement (Cluster Confirmation) |

TLS certificate verification is **ENABLED** on every gRPC connection (`grpc.credentials.createSsl`) using the peer's specific TLS CA root certificates and SSL target name override.

---

## 3. Privacy & Defense-in-Depth

The Gateway service enforces client-side defense-in-depth before sending proposals to Fabric. The following prohibited fields are rejected immediately:
- `victim_name`, `victim_phone`, `phone`, `phone_number`, `mobile`
- `account_number`, `raw_account_number`, `bank_account`
- `upi_id`, `vpa`, `aadhaar`, `pan`
- `password`, `jwt`, `token`, `raw_transaction_history`, `raw_complaint`

---

## 4. Truthful Failure & Fault Tolerance

If the Fabric peer or ordering service becomes unavailable:
- The Gateway immediately returns `503 Service Unavailable` with error code `FABRIC_UNAVAILABLE`.
- **NO FAKE FALLBACKS:** No synthetic signals, mocked responses, or hardcoded hashes are returned.
- Upon Fabric peer restoration, the Gateway automatically reconnects without application restart or re-enrollment.

---

## 5. Usage & Development Commands

### Installation
```bash
cd blockchain/gateway
npm install
```

### Unit Tests
```bash
npm test
```

### Running Simulation Scripts
```bash
# Submit signal as BankA
node scripts/bank-a-submit.js

# Submit corroborating signal as BankB
node scripts/bank-b-submit.js

# Submit law-enforcement confirmation as LEA
node scripts/lea-submit.js

# Query ledger as I4C intelligence consumer
node scripts/i4c-query.js

# Run full end-to-end B.3 gateway verification suite
node scripts/gateway-smoke-test.js
```

### Starting the Local Gateway HTTP API
```bash
npm start
# Listens on http://0.0.0.0:4000
```

### Available Endpoints
- `GET /health` — Local Gateway process status
- `GET /api/v1/gateway/health` — Live Fabric peer & ledger accessibility probe
- `GET /api/v1/signals/:eventId` — Retrieve signal by ID
- `GET /api/v1/signals/:eventId/state` — Query current lifecycle state (ACTIVE / CORRECTED / REVOKED)
- `GET /api/v1/signals/:eventId/history` — Full immutable ledger transaction history
- `GET /api/v1/signals/cluster/:clusterId` — Query active signals for a specific spatial cluster
- `GET /api/v1/signals/subject/:opaqueSubjectRef` — Query signals for an opaque subject reference
- `GET /api/v1/signals/time-window?start=...&end=...` — Query signals within ISO-8601 time window
