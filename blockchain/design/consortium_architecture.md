# CyberShield AI — Hyperledger Fabric Consortium Architecture

## 1. Consortium Overview
The CyberShield AI Blockchain layer provides a decentralized, tamper-evident audit and coordination fabric across simulated banking institutions and enforcement agencies:

* **BankA (BankAMSP)**: Prototype commercial bank submitting cash-out anomaly signals.
* **BankB (BankBMSP)**: Prototype commercial bank submitting corridor signals.
* **BankC (BankCMSP)**: Prototype commercial bank submitting ATM withdrawal alerts.
* **I4C (I4CMSP)**: National Cybercrime Coordination Centre querying cross-organization intelligence.
* **LEA (LEAMSP)**: Law Enforcement Agency querying verified cash-out clusters and intervention records.
* **Orderer (OrdererMSP)**: Crash Fault Tolerant (CFT) Raft ordering node (`orderer.cybershield.net`).

## 2. Channel Architecture
* **Channel Name**: `cyber-intelligence`
* **Consensus**: Raft (etcdraft) single-orderer node for local prototype/demo.
* **Capabilities**: Channel V2_0, Application V2_5.

## 3. Privacy & Anti-PII Invariant
The blockchain layer enforces strict data privacy:
* **NO Raw PII**: Names, phone numbers, raw account numbers, UPI IDs, passwords, and JWT tokens are NEVER committed to ledger state.
* **Opaque Intelligence**: Only opaque case IDs (`CMP-NEW-XXXXXX`), hashed account signatures, ATM cluster IDs, timestamps, and confidence scores are written to the ledger.
* **Private Data Collections**: Reserved for institution-sensitive transaction hashes.

## 4. ML Independence & Safety
* Blockchain is strictly an immutable coordination and intelligence sharing layer.
* It does NOT replace or contain the XGBoost V7-compat inference pipeline.
* The existing production ML pipeline (`cashout-location-xgb-v7-compat`) remains the authoritative predictor.
