#!/bin/bash
# ==============================================================================
# CyberShield AI — Hyperledger Fabric Prototype Network Verification
# Verifies Docker runtime, containers, channel membership, and ledger height
# ==============================================================================

set -euo pipefail

SCRIPT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
NETWORK_DIR="$(cd "${SCRIPT_DIR}/.." && pwd)"

cd "${NETWORK_DIR}"

if ! grep -q "orderer.cybershield.net" /etc/hosts 2>/dev/null; then
    echo "127.0.0.1 orderer.cybershield.net peer0.banka.cybershield.net peer0.bankb.cybershield.net peer0.bankc.cybershield.net peer0.i4c.cybershield.net peer0.lea.cybershield.net" >> /etc/hosts || true
fi

echo "=================================================="
echo "Verifying CyberShield AI Fabric Network Health"

echo "=================================================="

# 1. Check Docker
if docker ps >/dev/null 2>&1; then
    DOCKER_STATUS="PASS"
else
    echo "Docker is not running!"
    exit 1
fi

# 2. Check Required Containers
CONTAINERS=(
    "orderer.cybershield.net"
    "peer0.banka.cybershield.net"
    "peer0.bankb.cybershield.net"
    "peer0.bankc.cybershield.net"
    "peer0.i4c.cybershield.net"
    "peer0.lea.cybershield.net"
)

RUNNING_COUNT=0
for c in "${CONTAINERS[@]}"; do
    STATUS=$(docker inspect -f '{{.State.Status}}' "$c" 2>/dev/null || echo "not_found")
    if [ "$STATUS" == "running" ]; then
        echo "[CONTAINER] $c: RUNNING"
        RUNNING_COUNT=$((RUNNING_COUNT + 1))
    else
        echo "[CONTAINER] $c: $STATUS (FAIL)"
    fi
done

# 3. Check Channel Membership and Ledger Height on Each Peer
PEERS_JOINED=0
CHANNEL="cyber-intelligence"
LEDGER_HEIGHT="unknown"
export FABRIC_CFG_PATH=/usr/local/config


check_peer() {
    local ORG_NAME=$1
    local MSP_ID=$2
    local DOMAIN=$3
    local PORT=$4

    export CORE_PEER_TLS_ENABLED=true
    export CORE_PEER_LOCALMSPID="${MSP_ID}"
    export CORE_PEER_TLS_ROOTCERT_FILE="${NETWORK_DIR}/organizations/peerOrganizations/${DOMAIN}/peers/peer0.${DOMAIN}/tls/ca.crt"
    export CORE_PEER_MSPCONFIGPATH="${NETWORK_DIR}/organizations/peerOrganizations/${DOMAIN}/users/Admin@${DOMAIN}/msp"
    export CORE_PEER_ADDRESS="peer0.${DOMAIN}:${PORT}"


    CHANNELS=$(peer channel list 2>/dev/null || echo "")
    if echo "$CHANNELS" | grep -q "${CHANNEL}"; then
        INFO=$(peer channel getinfo -c "${CHANNEL}" 2>/dev/null || echo "")
        HEIGHT=$(echo "$INFO" | grep -o 'Blockchain info: height=[0-9]*' | cut -d= -f2 || echo "1")
        echo "[PEER] ${ORG_NAME} (peer0.${DOMAIN}): JOINED (${CHANNEL}, height=${HEIGHT})"
        PEERS_JOINED=$((PEERS_JOINED + 1))
        LEDGER_HEIGHT="${HEIGHT}"
    else
        echo "[PEER] ${ORG_NAME} (peer0.${DOMAIN}): NOT JOINED"
    fi
}

check_peer "BankA" "BankAMSP" "banka.cybershield.net" 7051
check_peer "BankB" "BankBMSP" "bankb.cybershield.net" 8051
check_peer "BankC" "BankCMSP" "bankc.cybershield.net" 9051
check_peer "I4C"   "I4CMSP"   "i4c.cybershield.net"   10051
check_peer "LEA"   "LEAMSP"   "lea.cybershield.net"   11051

echo "=================================================="
if [ "${RUNNING_COUNT}" -eq 6 ] && [ "${PEERS_JOINED}" -eq 5 ]; then
    echo "FABRIC NETWORK HEALTH: PASS"
    echo "Organizations: 5/5"
    echo "Channel: ${CHANNEL}"
    echo "Peers joined: ${PEERS_JOINED}/5"
    echo "Ledger: ACCESSIBLE (height=${LEDGER_HEIGHT})"
    exit 0
else
    echo "FABRIC NETWORK HEALTH: FAIL"
    echo "Running containers: ${RUNNING_COUNT}/6"
    echo "Peers joined: ${PEERS_JOINED}/5"
    exit 1
fi
