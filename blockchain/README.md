# CyberShield AI — Blockchain Consortium Subsystem

## Overview

This directory contains the architecture, security models, schemas, and implementation plans for the **Hyperledger Fabric** consortium subsystem of CyberShield AI (SIH 26184).

The blockchain subsystem serves as a decentralized, tamper-evident intelligence layer across participating financial institutions, the Indian Cyber Crime Coordination Centre (I4C), and Law Enforcement Agencies (LEA).

---

## Participating Organizations (Simulated Prototype)

1. **BankA (Lead Commercial Bank)**: Submits verified ATM withdrawal confirmation/attempt signals.
2. **BankB (Partner PSU Bank)**: Submits verified branch cash-out and mule account activity signals.
3. **BankC (Private Sector Bank)**: Corroborates inter-bank mule transaction chains.
4. **I4C (Central Coordinating Agency)**: Submits national cyber fraud advisories and anchors prediction audit hashes.
5. **LEA (Delhi Police Cyber Cell)**: Submits confirmed field investigation cluster outcomes and validates alert dispatch evidence.

> **Transparent Prototype Disclosure**: All organizational certificates, peer nodes, and consortium transactions are executed in a simulated local network environment for prototype demonstration. No live banking APIs or official NCRP servers are connected.

---

## Subdirectory Structure

```
blockchain/
├── README.md                                 # This file: Subsystem overview & directory layout
├── network/                                  # (Phase B.1) Fabric network configuration & crypto-config
├── chaincode/                                # (Phase B.2) Smart contracts
│   └── geo-intelligence/                     # GeoIntelligenceContract (Go / Node.js)
├── gateway/                                  # (Phase B.3) Node.js Fabric Gateway service
├── feature-engine/                           # (Phase B.4) Blockchain feature extraction pipeline
├── scripts/                                  # (Phase B.1) Network lifecycle and testing scripts
├── test-network/                             # (Phase B.1) Local multi-peer testbed
└── design/                                   # Frozen Phase A.4O Architecture & Contract Specifications
    ├── blockchain_intelligence_architecture.md
    ├── blockchain_event_schema.json
    ├── blockchain_feature_contract.json
    ├── blockchain_security_model.md
    ├── blockchain_access_control.md
    ├── prediction_hash_contract.json
    ├── failure_policy.md
    └── implementation_plan.md
```

---

## Core Guiding Principles

- **Additive**: Operates strictly downstream or parallel to the frozen `cashout-location-xgb-v4` ML pipeline.
- **Fail-Open**: An outage of Fabric peers or the gateway service never halts or degrades core triage, complaint persistence, or official ML predictions.
- **Privacy-Preserving**: Zero victim PII, plain-text account numbers, or narrative incident summaries are ever written to the immutable ledger.
- **Shadow-First**: Experimental blockchain-derived re-ranking runs purely in shadow mode until rigorous Phase B promotion gates are passed.
