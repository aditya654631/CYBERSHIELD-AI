#!/bin/bash
# ==============================================================================
# CyberShield AI — Safe Network Restart & Persistence Verification
# Restarts network containers preserving ledger state volumes
# ==============================================================================

set -euo pipefail

SCRIPT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
NETWORK_DIR="$(cd "${SCRIPT_DIR}/.." && pwd)"

cd "${NETWORK_DIR}"

if ! grep -q "orderer.cybershield.net" /etc/hosts 2>/dev/null; then
    echo "127.0.0.1 orderer.cybershield.net peer0.banka.cybershield.net peer0.bankb.cybershield.net peer0.bankc.cybershield.net peer0.i4c.cybershield.net peer0.lea.cybershield.net" | sudo tee -a /etc/hosts >/dev/null || true
fi

export FABRIC_CFG_PATH=/usr/local/config
CHANNEL_NAME="cyber-intelligence"
CC_NAME="geo-intelligence"

PEER0_BANKA_CA="${NETWORK_DIR}/organizations/peerOrganizations/banka.cybershield.net/peers/peer0.banka.cybershield.net/tls/ca.crt"

echo "=================================================="
echo "Testing Safe Network Restart & Ledger Persistence"
echo "=================================================="

echo "--- 1. Stopping containers (preserving volumes) ---"
docker compose stop

echo "--- 2. Starting containers back up ---"
docker compose start

echo "--- 3. Waiting for services to stabilize ---"
sleep 5

echo "--- 4. Verifying channel and chaincode availability ---"
export CORE_PEER_TLS_ENABLED=true
export CORE_PEER_LOCALMSPID="BankAMSP"
export CORE_PEER_TLS_ROOTCERT_FILE="${PEER0_BANKA_CA}"
export CORE_PEER_MSPCONFIGPATH="${NETWORK_DIR}/organizations/peerOrganizations/banka.cybershield.net/users/Admin@banka.cybershield.net/msp"
export CORE_PEER_ADDRESS="peer0.banka.cybershield.net:7051"

HEIGHT=$(peer channel getinfo -c "${CHANNEL_NAME}" | grep -o '"height":[0-9]*' | awk -F: '{print $2}')
echo "Channel ${CHANNEL_NAME} height after restart: ${HEIGHT}"

QUERY_RES=$(peer chaincode query -C "${CHANNEL_NAME}" -n "${CC_NAME}" -c '{"function":"GetSignal","Args":["EVT-LIVE-BANKA-001"]}')
echo "Query result after restart: ${QUERY_RES}"

if echo "${QUERY_RES}" | grep -q "EVT-LIVE-BANKA-001"; then
    echo "[PASS] Restart persistence verified: Chaincode and state intact."
else
    echo "[FAIL] Failed to retrieve signal after restart."
    exit 1
fi
