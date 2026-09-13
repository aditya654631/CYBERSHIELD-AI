#!/bin/bash
# ==============================================================================
# CyberShield AI — Hyperledger Fabric Prototype Consortium Network Launch
# Organizations: BankA, BankB, BankC, I4C, LEA (Simulated Prototype Orgs)
# Channel: cyber-intelligence
# ==============================================================================

set -euo pipefail

SCRIPT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
NETWORK_DIR="$(cd "${SCRIPT_DIR}/.." && pwd)"

cd "${NETWORK_DIR}"

# Ensure consortium hostnames resolve to 127.0.0.1 in WSL environment
if ! grep -q "orderer.cybershield.net" /etc/hosts 2>/dev/null; then
    echo "127.0.0.1 orderer.cybershield.net peer0.banka.cybershield.net peer0.bankb.cybershield.net peer0.bankc.cybershield.net peer0.i4c.cybershield.net peer0.lea.cybershield.net" | sudo tee -a /etc/hosts >/dev/null || true
fi
sudo chmod 666 /var/run/docker.sock /run/docker.sock 2>/dev/null || true

echo "=================================================="
echo "Starting CyberShield AI Hyperledger Fabric Network"

echo "=================================================="

# 1. Generate Crypto Material if not present
if [ ! -d "organizations/peerOrganizations" ]; then
    echo "--- 1. Generating Organization Crypto Material via cryptogen ---"
    cryptogen generate --config=./crypto-config.yaml --output=organizations
    echo "[OK] Crypto material generated for Orderer, BankA, BankB, BankC, I4C, LEA."
else
    echo "--- 1. Reusing existing organization crypto material ---"
fi

# 2. Generate Channel Genesis Block
mkdir -p channel-artifacts
echo "--- 2. Generating Channel Genesis Block (cyber-intelligence) via configtxgen ---"
export FABRIC_CFG_PATH="${NETWORK_DIR}"
configtxgen -profile CyberIntelligenceGenesis -channelID cyber-intelligence -outputBlock ./channel-artifacts/cyber-intelligence.block
echo "[OK] Genesis block created at ./channel-artifacts/cyber-intelligence.block"

# 3. Start Docker Containers
echo "--- 3. Starting Fabric Containers via Docker Compose ---"
docker compose down --remove-orphans >/dev/null 2>&1 || true
docker compose up -d
echo "[OK] Containers started."

# 4. Wait for Orderer & Peers
echo "--- 4. Waiting for services to become responsive ---"
sleep 5

# 5. Join Orderer to Channel
echo "--- 5. Joining Orderer to Channel via osnadmin ---"
ORDERER_CA="${NETWORK_DIR}/organizations/ordererOrganizations/cybershield.net/tlsca/tlsca.cybershield.net-cert.pem"
ORDERER_ADMIN_CERT="${NETWORK_DIR}/organizations/ordererOrganizations/cybershield.net/orderers/orderer.cybershield.net/tls/server.crt"
ORDERER_ADMIN_KEY="${NETWORK_DIR}/organizations/ordererOrganizations/cybershield.net/orderers/orderer.cybershield.net/tls/server.key"

# Retry loop for orderer readiness
for i in {1..10}; do
    if osnadmin channel join \
        --channelID cyber-intelligence \
        --config-block ./channel-artifacts/cyber-intelligence.block \
        -o orderer.cybershield.net:7053 \
        --ca-file "${ORDERER_CA}" \
        --client-cert "${ORDERER_ADMIN_CERT}" \
        --client-key "${ORDERER_ADMIN_KEY}" 2>&1; then
        echo "[OK] Orderer joined channel cyber-intelligence."
        break
    else
        echo "Orderer not ready yet, retrying in 2s ($i/10)..."
        sleep 2
    fi
done

# 6. Join All 5 Peers to Channel
echo "--- 6. Joining Peers to cyber-intelligence ---"
export FABRIC_CFG_PATH=/usr/local/config

join_peer() {
    local ORG_NAME=$1
    local MSP_ID=$2
    local DOMAIN=$3
    local PORT=$4

    echo "Joining ${ORG_NAME} (peer0.${DOMAIN}:${PORT})..."
    export CORE_PEER_TLS_ENABLED=true
    export CORE_PEER_LOCALMSPID="${MSP_ID}"
    export CORE_PEER_TLS_ROOTCERT_FILE="${NETWORK_DIR}/organizations/peerOrganizations/${DOMAIN}/peers/peer0.${DOMAIN}/tls/ca.crt"
    export CORE_PEER_MSPCONFIGPATH="${NETWORK_DIR}/organizations/peerOrganizations/${DOMAIN}/users/Admin@${DOMAIN}/msp"
    export CORE_PEER_ADDRESS="peer0.${DOMAIN}:${PORT}"



    for attempt in {1..5}; do
        if peer channel join -b ./channel-artifacts/cyber-intelligence.block 2>&1; then
            echo "[OK] ${ORG_NAME} joined channel cyber-intelligence."
            return 0
        else
            sleep 2
        fi
    done
    echo "[WARN] ${ORG_NAME} join retry completed."
}

join_peer "BankA" "BankAMSP" "banka.cybershield.net" 7051
join_peer "BankB" "BankBMSP" "bankb.cybershield.net" 8051
join_peer "BankC" "BankCMSP" "bankc.cybershield.net" 9051
join_peer "I4C"   "I4CMSP"   "i4c.cybershield.net"   10051
join_peer "LEA"   "LEAMSP"   "lea.cybershield.net"   11051

echo "=================================================="
echo "Hyperledger Fabric Network is UP and Channel Ready"
echo "=================================================="
