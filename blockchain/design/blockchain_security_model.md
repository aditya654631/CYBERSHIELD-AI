# BLOCKCHAIN SECURITY & PRIVACY MODEL — HYPERLEDGER FABRIC

## 1. Threat Modeling & Security Objectives

The CyberShield AI consortium ledger bridges commercial banks and law enforcement. The security model addresses the following core threats:

1. **Victim PII Exposure**: Leakage of citizen identity, phone numbers, or residential addresses across bank competitors.
2. **Commercial Surveillance**: Competitor banks deducing transaction volumes, liquidity, or customer lists of rival banks.
3. **Signal Tampering / Forgery**: Rogue or compromised actors injecting false cash-out signals to mislead police field deployments.
4. **Historical Revisionism**: Altering past records to conceal bank operational delay or investigator oversight.
5. **Future Signal Leakage**: Models extracting ledger events occurring after a complaint was registered, leading to synthetic performance inflation.

---

## 2. Cryptographic Privacy Mechanisms

### A. Pseudonymization via Keyed HMAC
- Raw account numbers, IFSC codes, and citizen IDs are never written to ledger state.
- Accounts are mapped to `opaque_subject_ref = HMAC-SHA256(Account_Number, Consortium_Salt)`.
- The `Consortium_Salt` is managed via hardware security modules (HSM) or secure vault enclaves.

### B. Spatial Generalization
- Cash-out locations are submitted at the **Macro Cluster Level** (cluster ID 0–40, corresponding to defined commercial hub sectors) rather than exact GPS latitude/longitude or ATM serial numbers.

### C. Private Data Collections (PDCs)
- Sensitive corroboration evidence (e.g. internal transaction sequence numbers, CCTV reference hashes) is stored within bilateral Private Data Collections between the submitting bank and LEA/I4C.
- Only the cryptographic state hash is committed to the shared channel ledger.

---

## 3. Identity, Authentication & Public Key Infrastructure (PKI)

- **Fabric MSP (Membership Service Provider)**: Every participating organization operates its own Certificate Authority (`rca-banka`, `rca-bankb`, `rca-i4c`, `rca-lea`).
- **Mutual TLS (mTLS)**: All communication between the FastAPI backend, Fabric Gateway service, peers, and orderers requires TLS 1.3 with client certificate validation.
- **Transaction Signatures**: Every ledger invocation is cryptographically signed by an authorized client identity. Unsigned or improperly endorsed transactions are rejected during the ordering phase.

---

## 4. Signal Revocation & Correction Integrity

- Smart contracts forbid in-place mutation or deletion of ledger history.
- To correct a signal, a member must invoke `CorrectSignal`, which writes a new transaction pointing to `previous_event_ref`.
- To revoke an erroneous signal, `RevokeSignal` marks the state as `REVOKED`. The raw history remains visible in the blockchain audit trail, while feature engines filter out the revoked state.
- Only the original submitting organization (or authorized I4C root MSP) has permission to invoke `CorrectSignal` or `RevokeSignal` for a given `event_id`.
