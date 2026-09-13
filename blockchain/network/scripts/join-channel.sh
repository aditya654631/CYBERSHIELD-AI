#!/bin/bash
# ==============================================================================
# CyberShield AI — Join Peers to Channel Script
# Channel: cyber-intelligence
# Orgs: BankA, BankB, BankC, I4C, LEA
# ==============================================================================

set -euo pipefail

SCRIPT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
NETWORK_DIR="$(cd "${SCRIPT_DIR}/.." && pwd)"

cd "${NETWORK_DIR}"

export FABRIC_CFG_PATH=/usr/local/config
BLOCK_FILE="./channel-artifacts/cyber-intelligence.block"


if [ ! -f "${BLOCK_FILE}" ]; then
    echo "Error: ${BLOCK_FILE} not found. Run create-channel.sh first."
    exit 1
fi

join_org_peer() {
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


    peer channel join -b "${BLOCK_FILE}"
    echo "[OK] ${ORG_NAME} joined cyber-intelligence."
}

join_org_peer "BankA" "BankAMSP" "banka.cybershield.net" 7051
join_org_peer "BankB" "BankBMSP" "bankb.cybershield.net" 8051
join_org_peer "BankC" "BankCMSP" "bankc.cybershield.net" 9051
join_org_peer "I4C"   "I4CMSP"   "i4c.cybershield.net"   10051
join_org_peer "LEA"   "LEAMSP"   "lea.cybershield.net"   11051

echo "All 5 consortium peers joined channel cyber-intelligence successfully."
