#!/bin/bash
# ==============================================================================
# CyberShield AI — Package, Install, Approve, and Commit Geo-Intelligence Chaincode
# Channel: cyber-intelligence
# Orgs: BankA, BankB, BankC, I4C, LEA
# ==============================================================================

set -euo pipefail

SCRIPT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
NETWORK_DIR="$(cd "${SCRIPT_DIR}/.." && pwd)"
BLOCKCHAIN_DIR="$(cd "${NETWORK_DIR}/.." && pwd)"

cd "${NETWORK_DIR}"

if ! grep -q "orderer.cybershield.net" /etc/hosts 2>/dev/null; then
    echo "127.0.0.1 orderer.cybershield.net peer0.banka.cybershield.net peer0.bankb.cybershield.net peer0.bankc.cybershield.net peer0.i4c.cybershield.net peer0.lea.cybershield.net" | sudo tee -a /etc/hosts >/dev/null || true
fi

export FABRIC_CFG_PATH=/usr/local/config

CHANNEL_NAME="cyber-intelligence"
CC_NAME="geo-intelligence"
CC_VERSION="1.0"
CC_SEQUENCE="1"
CC_SRC_PATH="${BLOCKCHAIN_DIR}/chaincode/geo-intelligence"
CC_LABEL="${CC_NAME}_${CC_VERSION}"
CC_PACKAGE="${NETWORK_DIR}/channel-artifacts/${CC_LABEL}.tar.gz"

ORDERER_CA="${NETWORK_DIR}/organizations/ordererOrganizations/cybershield.net/orderers/orderer.cybershield.net/msp/tlscacerts/tlsca.cybershield.net-cert.pem"
PEER0_BANKA_CA="${NETWORK_DIR}/organizations/peerOrganizations/banka.cybershield.net/peers/peer0.banka.cybershield.net/tls/ca.crt"
PEER0_BANKB_CA="${NETWORK_DIR}/organizations/peerOrganizations/bankb.cybershield.net/peers/peer0.bankb.cybershield.net/tls/ca.crt"
PEER0_BANKC_CA="${NETWORK_DIR}/organizations/peerOrganizations/bankc.cybershield.net/peers/peer0.bankc.cybershield.net/tls/ca.crt"
PEER0_I4C_CA="${NETWORK_DIR}/organizations/peerOrganizations/i4c.cybershield.net/peers/peer0.i4c.cybershield.net/tls/ca.crt"
PEER0_LEA_CA="${NETWORK_DIR}/organizations/peerOrganizations/lea.cybershield.net/peers/peer0.lea.cybershield.net/tls/ca.crt"

SIGNATURE_POLICY="OutOf(2, 'BankAMSP.peer', 'BankBMSP.peer', 'BankCMSP.peer', 'I4CMSP.peer', 'LEAMSP.peer')"

set_org_env() {
    local ORG=$1
    export CORE_PEER_TLS_ENABLED=true
    case $ORG in
        BankA)
            export CORE_PEER_LOCALMSPID="BankAMSP"
            export CORE_PEER_TLS_ROOTCERT_FILE="${PEER0_BANKA_CA}"
            export CORE_PEER_MSPCONFIGPATH="${NETWORK_DIR}/organizations/peerOrganizations/banka.cybershield.net/users/Admin@banka.cybershield.net/msp"
            export CORE_PEER_ADDRESS="peer0.banka.cybershield.net:7051"
            ;;
        BankB)
            export CORE_PEER_LOCALMSPID="BankBMSP"
            export CORE_PEER_TLS_ROOTCERT_FILE="${PEER0_BANKB_CA}"
            export CORE_PEER_MSPCONFIGPATH="${NETWORK_DIR}/organizations/peerOrganizations/bankb.cybershield.net/users/Admin@bankb.cybershield.net/msp"
            export CORE_PEER_ADDRESS="peer0.bankb.cybershield.net:8051"
            ;;
        BankC)
            export CORE_PEER_LOCALMSPID="BankCMSP"
            export CORE_PEER_TLS_ROOTCERT_FILE="${PEER0_BANKC_CA}"
            export CORE_PEER_MSPCONFIGPATH="${NETWORK_DIR}/organizations/peerOrganizations/bankc.cybershield.net/users/Admin@bankc.cybershield.net/msp"
            export CORE_PEER_ADDRESS="peer0.bankc.cybershield.net:9051"
            ;;
        I4C)
            export CORE_PEER_LOCALMSPID="I4CMSP"
            export CORE_PEER_TLS_ROOTCERT_FILE="${PEER0_I4C_CA}"
            export CORE_PEER_MSPCONFIGPATH="${NETWORK_DIR}/organizations/peerOrganizations/i4c.cybershield.net/users/Admin@i4c.cybershield.net/msp"
            export CORE_PEER_ADDRESS="peer0.i4c.cybershield.net:10051"
            ;;
        LEA)
            export CORE_PEER_LOCALMSPID="LEAMSP"
            export CORE_PEER_TLS_ROOTCERT_FILE="${PEER0_LEA_CA}"
            export CORE_PEER_MSPCONFIGPATH="${NETWORK_DIR}/organizations/peerOrganizations/lea.cybershield.net/users/Admin@lea.cybershield.net/msp"
            export CORE_PEER_ADDRESS="peer0.lea.cybershield.net:11051"
            ;;
        *)
            echo "Unknown org: $ORG"
            exit 1
            ;;
    esac
}

echo "=================================================="
echo "Phase B.2: Deploying Geo-Intelligence Chaincode"
echo "=================================================="

# 1. Package Chaincode
echo "--- 1. Packaging Chaincode (${CC_LABEL}) ---"
mkdir -p "${NETWORK_DIR}/channel-artifacts"
set_org_env "BankA"
peer lifecycle chaincode package "${CC_PACKAGE}" \
    --path "${CC_SRC_PATH}" \
    --lang node \
    --label "${CC_LABEL}"
echo "[OK] Chaincode packaged at ${CC_PACKAGE}"

# 2. Install on all 5 Peers
echo "--- 2. Installing on all 5 Consortium Peers ---"
for ORG in BankA BankB BankC I4C LEA; do
    echo "Installing on ${ORG}..."
    set_org_env "${ORG}"
    peer lifecycle chaincode install "${CC_PACKAGE}"
    echo "[OK] Installed on ${ORG}"
done

# 3. Query Installed and Determine Package ID
echo "--- 3. Querying Package ID ---"
set_org_env "BankA"
PACKAGE_ID=$(peer lifecycle chaincode queryinstalled | grep "${CC_LABEL}" | awk '{print $3}' | sed 's/,//')
echo "Discovered Package ID: ${PACKAGE_ID}"

if [ -z "${PACKAGE_ID}" ]; then
    echo "Error: Failed to determine Package ID."
    exit 1
fi

# 4. Approve for each Org
echo "--- 4. Approving Chaincode Definition (5/5 Orgs) ---"
for ORG in BankA BankB BankC I4C LEA; do
    echo "Approving for ${ORG}..."
    set_org_env "${ORG}"
    peer lifecycle chaincode approveformyorg \
        -o orderer.cybershield.net:7050 \
        --ordererTLSHostnameOverride orderer.cybershield.net \
        --tls \
        --cafile "${ORDERER_CA}" \
        --channelID "${CHANNEL_NAME}" \
        --name "${CC_NAME}" \
        --version "${CC_VERSION}" \
        --package-id "${PACKAGE_ID}" \
        --sequence "${CC_SEQUENCE}" \
        --signature-policy "${SIGNATURE_POLICY}"
    echo "[OK] Approved for ${ORG}"
done

# 5. Check Commit Readiness
echo "--- 5. Checking Commit Readiness ---"
set_org_env "BankA"
peer lifecycle chaincode checkcommitreadiness \
    --channelID "${CHANNEL_NAME}" \
    --name "${CC_NAME}" \
    --version "${CC_VERSION}" \
    --sequence "${CC_SEQUENCE}" \
    --signature-policy "${SIGNATURE_POLICY}" \
    --output json

# 6. Commit Chaincode Definition
echo "--- 6. Committing Chaincode Definition to ${CHANNEL_NAME} ---"
peer lifecycle chaincode commit \
    -o orderer.cybershield.net:7050 \
    --ordererTLSHostnameOverride orderer.cybershield.net \
    --tls \
    --cafile "${ORDERER_CA}" \
    --channelID "${CHANNEL_NAME}" \
    --name "${CC_NAME}" \
    --version "${CC_VERSION}" \
    --sequence "${CC_SEQUENCE}" \
    --signature-policy "${SIGNATURE_POLICY}" \
    --peerAddresses peer0.banka.cybershield.net:7051 --tlsRootCertFiles "${PEER0_BANKA_CA}" \
    --peerAddresses peer0.bankb.cybershield.net:8051 --tlsRootCertFiles "${PEER0_BANKB_CA}" \
    --peerAddresses peer0.bankc.cybershield.net:9051 --tlsRootCertFiles "${PEER0_BANKC_CA}" \
    --peerAddresses peer0.i4c.cybershield.net:10051 --tlsRootCertFiles "${PEER0_I4C_CA}" \
    --peerAddresses peer0.lea.cybershield.net:11051 --tlsRootCertFiles "${PEER0_LEA_CA}"
echo "[OK] Chaincode committed."

# 7. Query Committed on all Peers
echo "--- 7. Verifying QueryCommitted ---"
for ORG in BankA BankB BankC I4C LEA; do
    set_org_env "${ORG}"
    echo "Querying committed on ${ORG}:"
    peer lifecycle chaincode querycommitted --channelID "${CHANNEL_NAME}" --name "${CC_NAME}"
done

# 8. Initialize Ledger
echo "--- 8. Initializing Ledger (InitLedger) ---"
set_org_env "BankA"
peer chaincode invoke \
    -o orderer.cybershield.net:7050 \
    --ordererTLSHostnameOverride orderer.cybershield.net \
    --tls \
    --cafile "${ORDERER_CA}" \
    --channelID "${CHANNEL_NAME}" \
    --name "${CC_NAME}" \
    --peerAddresses peer0.banka.cybershield.net:7051 --tlsRootCertFiles "${PEER0_BANKA_CA}" \
    --peerAddresses peer0.i4c.cybershield.net:10051 --tlsRootCertFiles "${PEER0_I4C_CA}" \
    -c '{"function":"InitLedger","Args":[]}' \
    --waitForEvent

echo "=================================================="
echo "Geo-Intelligence Chaincode Successfully Deployed!"
echo "=================================================="
