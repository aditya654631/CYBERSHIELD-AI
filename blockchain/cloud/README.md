# CyberShield AI — 24×7 Cloud VPS Fabric Consortium Deployment Guide

This directory contains the production-grade cloud deployment architecture for migrating the CyberShield AI Hyperledger Fabric consortium from local WSL2/Docker to a dedicated 24×7 Ubuntu cloud VPS.

> [!NOTE]
> **Prototype Consortium Architecture**:
> Organizations **BankA, BankB, BankC, I4C, and LEA** participating in the `cyber-intelligence` channel are **simulated prototype consortium members** designed for the SIH 26184 national evaluation. No live private banking networks are contacted.

---

## 1. Target VPS Specifications

| Parameter | Recommended Specification | Minimum Requirement |
| :--- | :--- | :--- |
| **Operating System** | Ubuntu 22.04 / 24.04 LTS | Ubuntu 20.04+ LTS |
| **vCPU** | 4 – 8 vCPU | 4 vCPU |
| **Memory (RAM)** | 16 GB RAM | 8 GB RAM |
| **Storage (SSD)** | 80+ GB NVMe / SSD | 50 GB SSD |
| **Public Ports** | 22 (SSH), 80 (HTTP/ACME), 443 (HTTPS) | 22, 443 |
| **Internal Ports** | 7050–11052 (Fabric), 4000 (Gateway) | Isolated within Docker |

---

## 2. Directory Structure

```
blockchain/cloud/
├── docker-compose.cloud.yml         # Fabric 2.5 Orderer, 5 Peers, Gateway & Caddy
├── Caddyfile                        # Automated TLS termination & reverse proxy
├── .env.example                     # Environment configuration template
├── README.md                        # This operational guide
├── systemd/
│   └── cybershield-fabric.service   # Systemd unit for reboot auto-start
└── scripts/
    ├── cloud-bootstrap.sh           # Installs Docker, Node.js, UFW firewall & systemd
    ├── cloud-network-up.sh          # Boots consortium in FRESH_CLOUD_NETWORK mode
    ├── cloud-network-down.sh        # Non-destructive shutdown preserving volumes
    ├── cloud-network-restart.sh     # Safe restart with ledger continuity checks
    ├── cloud-health.sh              # Telemetry probe checking containers, ledger & auth
    ├── cloud-backup.sh              # Encrypted timestamped tarball of volumes & crypto
    └── cloud-restore.sh             # Full restore supporting MIGRATE_EXISTING_LEDGER
```

---

## 3. Deployment Modes

Before deployment, CyberShield AI supports two distinct ledger lifecycle modes:

### Mode A: `FRESH_CLOUD_NETWORK` (Default & Preferred for SIH)
- Generates clean cloud consortium crypto and initializes the `cyber-intelligence` genesis block.
- Starts fresh named volumes (`cybershield_orderer_ledger`, `cybershield_banka_ledger`, etc.).
- Installs, approves, and commits identical verified chaincodes (`geo-intelligence` v1.0, `prediction-audit` v1.0).
- Seeds controlled synthetic demo telemetry without carrying historical development artifacts.

### Mode B: `MIGRATE_EXISTING_LEDGER` (Optional Historical Migration)
- Preserves local ledger volumes and crypto identities via `./scripts/cloud-backup.sh`.
- Restores exact block continuity and prediction hashes on the cloud VPS via `./scripts/cloud-restore.sh <archive>`.

---

## 4. Step-by-Step Deployment Instructions

### Step 1: Provision Cloud VPS & Clone Repository
Log into your clean Ubuntu VPS:
```bash
ssh root@<vps-ip>
git clone https://github.com/aditya654631/CYBERSHIELD-AI.git /opt/cybershield
cd /opt/cybershield/blockchain/cloud
```

### Step 2: Run Host Bootstrap
Execute the automated host bootstrap script to install Docker, Node.js, and configure UFW firewall:
```bash
chmod +x scripts/*.sh
sudo ./scripts/cloud-bootstrap.sh
```

### Step 3: Configure Environment Variables
Copy and customize `.env`:
```bash
cp .env.example .env
nano .env
```
Ensure you configure:
- `DOMAIN`: Your VPS domain or subdomain (e.g. `fabric.yourdomain.com`).
- `GATEWAY_AUTH_TOKEN`: A strong 64-character token generated via `openssl rand -hex 32`.

### Step 4: Launch the Consortium Stack
Launch the network and chaincode deployments:
```bash
sudo ./scripts/cloud-network-up.sh
```

### Step 5: Verify Live Health
Probe all 6 consortium nodes, channel height, and Gateway health:
```bash
./scripts/cloud-health.sh
```

---

## 5. Security & Topology

### Enforced Traffic Flow:
```
[User Browser / Frontend]
          │
          ▼ HTTPS
[Railway FastAPI Backend]
          │
          ▼ HTTPS (Bearer Token Auth)
[Cloud VPS Caddy (Port 443)]
          │
          ▼ Internal Docker Network
[Fabric Gateway (Port 4000)]
          │
          ▼ gRPC / TLS
[Fabric Orderer & 5 Peers (Internal Network Only)]
```
- **Direct Frontend Access Blocked**: Web clients never interact directly with the Fabric Gateway or peers.
- **Firewall Isolation**: Peer gRPC ports (7050, 7051, 8051, 9051, 10051, 11051) are bound to `127.0.0.1` and blocked by UFW from external public access.
- **Service Token Authentication**: All prediction anchoring and telemetry query endpoints require `Authorization: Bearer <GATEWAY_AUTH_TOKEN>`.

---

## 6. Railway Backend Integration

Once the cloud Gateway passes health checks, update Railway FastAPI environment variables:

```bash
FABRIC_ENABLED=true
FABRIC_GATEWAY_URL=https://fabric.yourdomain.com/api/v1
FABRIC_GATEWAY_TOKEN=<your-configured-64-char-hex-token>
FABRIC_CHANNEL=cyber-intelligence
FABRIC_GEO_CHAINCODE=geo-intelligence
FABRIC_AUDIT_CHAINCODE=prediction-audit
```

---

## 7. Failure Isolation Policy

CyberShield AI enforces absolute failure isolation:
- If the cloud Fabric Gateway or VPS is temporarily unreachable, **official V7-compat predictions continue seamlessly**.
- Complaint registration, model scoring, Top-3 cash-out locations, Risk Map visualizations, and Alerts succeed with 100% availability.
- Prediction audit status records `PENDING` or `UNAVAILABLE` without transaction rollback or user interruption.
- Once cloud Fabric connectivity is restored, predictions can be audited/verified asynchronously.

---

## 8. Backup & Disaster Recovery

### Creating a Safe Backup:
```bash
sudo ./scripts/cloud-backup.sh
```
Creates a restricted archive (`chmod 600`) in `/var/backups/cybershield/` containing all ledger volumes, channel artifacts, and crypto MSPs.

### Restoring from Backup:
```bash
sudo ./scripts/cloud-restore.sh /var/backups/cybershield/cybershield_fabric_backup_<timestamp>.tar.gz
```
Restores all named volumes and starts the consortium stack cleanly.
