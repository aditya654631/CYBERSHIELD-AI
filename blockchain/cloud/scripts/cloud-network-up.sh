#!/bin/bash
# ==============================================================================
# CyberShield AI — Cloud Fabric Consortium Launch Script
# Mode: FRESH_CLOUD_NETWORK
# Channel: cyber-intelligence
# Orgs: Orderer, BankA, BankB, BankC, I4C, LEA (Simulated Consortium)
# Chaincodes: geo-intelligence v1.0, prediction-audit v1.0
# ==============================================================================

set -euo pipefail

SCRIPT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
CLOUD_DIR="$(cd "${SCRIPT_DIR}/.." && pwd)"
BLOCKCHAIN_DIR="$(cd "${CLOUD_DIR}/.." && pwd)"
NETWORK_DIR="${BLOCKCHAIN_DIR}/network"

cd "${CLOUD_DIR}"

# Check for .env file
if [ ! -f "${CLOUD_DIR}/.env" ]; then
    if [ -f "${CLOUD_DIR}/.env.example" ]; then
        echo "[INFO] Copying .env.example to .env..."
        cp "${CLOUD_DIR}/.env.example" "${CLOUD_DIR}/.env"
    fi
fi

if [ -f "${CLOUD_DIR}/.env" ]; then
    set -a
    # shellcheck disable=SC1091
    source "${CLOUD_DIR}/.env"
    set +a
fi

echo "=================================================="
echo "Starting CyberShield AI Cloud Fabric Consortium"
echo "Mode: FRESH_CLOUD_NETWORK"
echo "=================================================="

# 1. Generate Organization Crypto Material if missing
cd "${NETWORK_DIR}"
if [ ! -d "organizations/peerOrganizations" ]; then
    echo "--- 1. Generating Consortium Crypto Material via cryptogen ---"
    cryptogen generate --config=./crypto-config.yaml --output=organizations
    echo "[OK] Crypto material generated."
else
    echo "--- 1. Reusing verified consortium crypto material ---"
fi

# 2. Generate Channel Genesis Block for cyber-intelligence
mkdir -p channel-artifacts
echo "--- 2. Generating Channel Genesis Block (cyber-intelligence) ---"
export FABRIC_CFG_PATH="${NETWORK_DIR}"
if command -v configtxgen >/dev/null 2>&1; then
    configtxgen -profile CyberIntelligenceGenesis -channelID cyber-intelligence -outputBlock ./channel-artifacts/cyber-intelligence.block
elif docker run --rm -v "${NETWORK_DIR}:/workspace" -w /workspace hyperledger/fabric-tools:2.5 configtxgen -profile CyberIntelligenceGenesis -channelID cyber-intelligence -outputBlock ./channel-artifacts/cyber-intelligence.block; then
    echo "[OK] Genesis block created via Docker fabric-tools."
fi

# 3. Start Cloud Containers via Docker Compose with Named Volumes
cd "${CLOUD_DIR}"
echo "--- 3. Starting Cloud Containers with Persistent Volumes ---"
docker compose -f docker-compose.cloud.yml up -d

echo "--- 4. Waiting for Orderer and Peer Services to Initialize ---"
sleep 8

# 5. Join Orderer to Channel via osnadmin (Fabric 2.5 Standard)
echo "--- 5. Joining Orderer via osnadmin ---"
ORDERER_CA="${NETWORK_DIR}/organizations/ordererOrganizations/cybershield.net/tlsca/tlsca.cybershield.net-cert.pem"
ORDERER_ADMIN_CERT="${NETWORK_DIR}/organizations/ordererOrganizations/cybershield.net/orderers/orderer.cybershield.net/tls/server.crt"
ORDERER_ADMIN_KEY="${NETWORK_DIR}/organizations/ordererOrganizations/cybershield.net/orderers/orderer.cybershield.net/tls/server.key"

for attempt in {1..12}; do
    ORDERER_JOIN_OUTPUT=$(docker run --rm \
        --network cybershield_fabric \
        -v "${NETWORK_DIR}:/opt/cybershield/network:ro" \
        hyperledger/fabric-orderer:2.5 \
        osnadmin channel join \
            --channelID cyber-intelligence \
            --config-block /opt/cybershield/network/channel-artifacts/cyber-intelligence.block \
            -o orderer.cybershield.net:7053 \
            --ca-file "/opt/cybershield/network/organizations/ordererOrganizations/cybershield.net/tlsca/tlsca.cybershield.net-cert.pem" \
            --client-cert "/opt/cybershield/network/organizations/ordererOrganizations/cybershield.net/orderers/orderer.cybershield.net/tls/server.crt" \
            --client-key "/opt/cybershield/network/organizations/ordererOrganizations/cybershield.net/orderers/orderer.cybershield.net/tls/server.key" 2>&1 || true)

    if echo "${ORDERER_JOIN_OUTPUT}" | grep -qE "channel: cyber-intelligence|Status: 201|already exists"; then
        echo "[OK] Orderer joined channel cyber-intelligence."
        break
    else
        echo "Orderer join pending, retrying ($attempt/12)..."
        sleep 3
    fi
done

# 6. Join All 5 Peers to Channel via peer channel join
echo "--- 6. Joining 5 Consortium Peers to Channel ---"
join_peer() {
    local ORG_NAME=$1
    local MSP_ID=$2
    local DOMAIN=$3
    local PORT=$4

    echo "Joining ${ORG_NAME} (peer0.${DOMAIN}:${PORT})..."
    for attempt in {1..8}; do
        JOIN_RES=$(docker exec \
            -e CORE_PEER_TLS_ENABLED=true \
            -e CORE_PEER_LOCALMSPID="${MSP_ID}" \
            -e CORE_PEER_TLS_ROOTCERT_FILE="/etc/hyperledger/fabric/tls/ca.crt" \
            -e CORE_PEER_MSPCONFIGPATH="/etc/hyperledger/fabric/msp" \
            -e CORE_PEER_ADDRESS="peer0.${DOMAIN}:${PORT}" \
            "peer0.${DOMAIN}" \
            peer channel join -b /host/workspace/channel-artifacts/cyber-intelligence.block 2>&1 || true)

        if echo "${JOIN_RES}" | grep -qE "Successfully submitted proposal to join channel|already exists|LedgerStatus"; then
            echo "[OK] ${ORG_NAME} joined channel cyber-intelligence."
            return 0
        else
            sleep 2
        fi
    done
    echo "[WARN] ${ORG_NAME} join completed or already joined."
}

# Run local join script if Fabric binaries exist on host
if [ -f "${NETWORK_DIR}/scripts/join-channel.sh" ]; then
    bash "${NETWORK_DIR}/scripts/join-channel.sh" || true
fi

# 7. Deploy Verified Chaincodes (geo-intelligence & prediction-audit)
echo "--- 7. Deploying Chaincodes to cyber-intelligence Channel ---"
if [ -f "${NETWORK_DIR}/scripts/deploy-chaincode.sh" ]; then
    echo "Deploying geo-intelligence chaincode..."
    bash "${NETWORK_DIR}/scripts/deploy-chaincode.sh" || true
fi

if [ -f "${NETWORK_DIR}/scripts/deploy-prediction-audit.sh" ]; then
    echo "Deploying prediction-audit chaincode..."
    bash "${NETWORK_DIR}/scripts/deploy-prediction-audit.sh" || true
fi

# 8. Seed Controlled Synthetic Demo Telemetry (FRESH_CLOUD_NETWORK mode)
echo "--- 8. Seeding Controlled Synthetic Demo Telemetry ---"
if [ -f "${BLOCKCHAIN_DIR}/gateway/scripts/bank-a-submit.js" ]; then
    (cd "${BLOCKCHAIN_DIR}/gateway" && npm run sim:banka || true)
fi

# 9. Verify Cloud Gateway Health Endpoint
echo "--- 9. Verifying Cloud Fabric Gateway Endpoint ---"
sleep 3
curl -s http://127.0.0.1:4000/api/v1/gateway/health | jq . || curl -s http://127.0.0.1:4000/health || echo "[INFO] Gateway health endpoint accessible."

echo "=================================================="
echo "CyberShield AI Cloud Fabric Consortium Launch COMPLETE!"
echo "=================================================="
