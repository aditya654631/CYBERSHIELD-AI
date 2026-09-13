#!/bin/bash
# ==============================================================================
# CyberShield AI — Create Channel Script
# Channel: cyber-intelligence
# ==============================================================================

set -euo pipefail

SCRIPT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
NETWORK_DIR="$(cd "${SCRIPT_DIR}/.." && pwd)"

cd "${NETWORK_DIR}"

mkdir -p channel-artifacts
export FABRIC_CFG_PATH="${NETWORK_DIR}"

echo "Generating genesis block for channel 'cyber-intelligence'..."
configtxgen -profile CyberIntelligenceGenesis -channelID cyber-intelligence -outputBlock ./channel-artifacts/cyber-intelligence.block

ORDERER_CA="${NETWORK_DIR}/organizations/ordererOrganizations/cybershield.net/tlsca/tlsca.cybershield.net-cert.pem"
ORDERER_ADMIN_CERT="${NETWORK_DIR}/organizations/ordererOrganizations/cybershield.net/orderers/orderer.cybershield.net/tls/server.crt"
ORDERER_ADMIN_KEY="${NETWORK_DIR}/organizations/ordererOrganizations/cybershield.net/orderers/orderer.cybershield.net/tls/server.key"

echo "Joining Orderer to channel 'cyber-intelligence'..."
osnadmin channel join \
    --channelID cyber-intelligence \
    --config-block ./channel-artifacts/cyber-intelligence.block \
    -o orderer.cybershield.net:7053 \
    --ca-file "${ORDERER_CA}" \
    --client-cert "${ORDERER_ADMIN_CERT}" \
    --client-key "${ORDERER_ADMIN_KEY}"


echo "[OK] Channel 'cyber-intelligence' created and active on orderer."
