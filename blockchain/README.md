# CyberShield AI — Hyperledger Fabric Blockchain Network

## 1. Overview
This directory contains the Hyperledger Fabric v2.5 consortium prototype network for **CyberShield AI (SIH26184)**.

The network links 5 simulated prototype organizations:
* **BankA**: Prototype commercial bank node (`peer0.banka.cybershield.net:7051`)
* **BankB**: Prototype commercial bank node (`peer0.bankb.cybershield.net:8051`)
* **BankC**: Prototype commercial bank node (`peer0.bankc.cybershield.net:9051`)
* **I4C**: Indian Cybercrime Coordination Centre node (`peer0.i4c.cybershield.net:10051`)
* **LEA**: Law Enforcement Agency node (`peer0.lea.cybershield.net:11051`)
* **Orderer**: Raft consensus ordering node (`orderer.cybershield.net:7050`)

**Consortium Channel**: `cyber-intelligence`

> **IMPORTANT DISCLAIMER**: All organizations in this prototype are SIMULATED for demonstration. No real bank or live government network connection is claimed.

---

## 2. Prerequisites
1. **Windows 10/11 with WSL2 (Ubuntu)** or Linux host.
2. **Docker Desktop** (with WSL integration enabled for Ubuntu) or Docker Engine on Linux.
3. **Hyperledger Fabric v2.5.9 binaries** (`peer`, `configtxgen`, `cryptogen`, `osnadmin`) installed in WSL `/usr/local/bin`.
4. **Node.js**: v20+ / v24+ for future Gateway client applications.

---

## 3. Verified Commands

### From Windows PowerShell:
```powershell
# 1. Start Network (launches containers, creates channel, joins all 5 peers)
.\blockchain\network\scripts\network-up.ps1

# 2. Verify Network & Ledger Health
.\blockchain\network\scripts\verify-network.ps1

# 3. View Running Containers
wsl -d Ubuntu -- docker ps --format "table {{.Names}}\t{{.Status}}\t{{.Ports}}"

# 4. Stop Network
.\blockchain\network\scripts\network-down.ps1
```

### From WSL2 Ubuntu / Bash:
```bash
# 1. Start Network
cd blockchain/network
./scripts/network-up.sh

# 2. Verify Network
./scripts/verify-network.sh

# 3. View Containers
docker ps

# 4. Stop Network
./scripts/network-down.sh
```

---

## 4. Privacy & Security Rules
* **No Raw PII**: Victim personal info, raw bank accounts, UPI IDs, passwords, and JWTs are never written to the ledger.
* **Opaque Intelligence**: Hashed identifiers, cluster indices, and anomaly risk scores only.
* **Production Safety**: The blockchain network is strictly additive and independent from the core FastAPI inference server (`cashout-location-xgb-v7-compat`).
