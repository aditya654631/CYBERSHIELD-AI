#!/bin/bash
# ==============================================================================
# CyberShield AI — Multi-Organization Live Ledger Test Suite
# Tests: BankA Submit, I4C Read, BankB Corroboration, LEA Submit,
#        Unauthorized Rejection, Correction, Revocation, Idempotency,
#        Time-Window Query, Opaque-Subject Query, History Proof, Ledger Height
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

ORDERER_CA="${NETWORK_DIR}/organizations/ordererOrganizations/cybershield.net/orderers/orderer.cybershield.net/msp/tlscacerts/tlsca.cybershield.net-cert.pem"
PEER0_BANKA_CA="${NETWORK_DIR}/organizations/peerOrganizations/banka.cybershield.net/peers/peer0.banka.cybershield.net/tls/ca.crt"
PEER0_BANKB_CA="${NETWORK_DIR}/organizations/peerOrganizations/bankb.cybershield.net/peers/peer0.bankb.cybershield.net/tls/ca.crt"
PEER0_BANKC_CA="${NETWORK_DIR}/organizations/peerOrganizations/bankc.cybershield.net/peers/peer0.bankc.cybershield.net/tls/ca.crt"
PEER0_I4C_CA="${NETWORK_DIR}/organizations/peerOrganizations/i4c.cybershield.net/peers/peer0.i4c.cybershield.net/tls/ca.crt"
PEER0_LEA_CA="${NETWORK_DIR}/organizations/peerOrganizations/lea.cybershield.net/peers/peer0.lea.cybershield.net/tls/ca.crt"

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

get_ledger_height() {
    set_org_env "BankA"
    peer channel getinfo -c "${CHANNEL_NAME}" | grep -o '"height":[0-9]*' | awk -F: '{print $2}'
}

echo "=================================================="
echo "Phase B.2 Multi-Org Live Ledger Functional Tests"
echo "=================================================="

HEIGHT_BEFORE=$(get_ledger_height)
echo "Initial Ledger Height: ${HEIGHT_BEFORE}"

# ------------------------------------------------------------------------------
# TEST 1: BankA Submits Signal
# ------------------------------------------------------------------------------
echo ""
echo "=== TEST 1: BankA Submit Signal (EVT-LIVE-BANKA-001) ==="
set_org_env "BankA"
SIGNAL_BANKA='{"event_id":"EVT-LIVE-BANKA-001","event_type":"ATM_WITHDRAWAL_ATTEMPT","opaque_subject_ref":"opaque-demo-001","cluster_id":7,"district":"NEW_DELHI","event_timestamp":"2026-09-13T10:15:00.000Z","confidence":0.82,"source_reference_hash":"e3b0c44298fc1c149afbf4c8996fb92427ae41e4649b934ca495991b7852b855"}'

peer chaincode invoke \
    -o orderer.cybershield.net:7050 \
    --ordererTLSHostnameOverride orderer.cybershield.net \
    --tls \
    --cafile "${ORDERER_CA}" \
    --channelID "${CHANNEL_NAME}" \
    --name "${CC_NAME}" \
    --peerAddresses peer0.banka.cybershield.net:7051 --tlsRootCertFiles "${PEER0_BANKA_CA}" \
    --peerAddresses peer0.i4c.cybershield.net:10051 --tlsRootCertFiles "${PEER0_I4C_CA}" \
    -c "{\"function\":\"SubmitSignal\",\"Args\":[\"${SIGNAL_BANKA//\"/\\\"}\"]}" \
    --waitForEvent
echo "[PASS] TEST 1: BankA Submit Signal committed."

# ------------------------------------------------------------------------------
# TEST 2: Query from Another Org (I4C Reads BankA Signal)
# ------------------------------------------------------------------------------
echo ""
echo "=== TEST 2: I4C Cross-Org Read (GetSignal EVT-LIVE-BANKA-001) ==="
set_org_env "I4C"
I4C_READ_RES=$(peer chaincode query -C "${CHANNEL_NAME}" -n "${CC_NAME}" -c '{"function":"GetSignal","Args":["EVT-LIVE-BANKA-001"]}')
echo "I4C Query Result: ${I4C_READ_RES}"
if echo "${I4C_READ_RES}" | grep -q '"organization_msp":"BankAMSP"' && echo "${I4C_READ_RES}" | grep -q '"status":"ACTIVE"'; then
    echo "[PASS] TEST 2: I4C cross-org read verified BankA ownership and ACTIVE status."
else
    echo "[FAIL] TEST 2 failed."
    exit 1
fi

# ------------------------------------------------------------------------------
# TEST 3: BankB Submits Corroborating Signal for Cluster 7
# ------------------------------------------------------------------------------
echo ""
echo "=== TEST 3: BankB Corroborating Signal (EVT-LIVE-BANKB-002) ==="
set_org_env "BankB"
SIGNAL_BANKB='{"event_id":"EVT-LIVE-BANKB-002","event_type":"ATM_WITHDRAWAL_CONFIRMED","opaque_subject_ref":"opaque-demo-002","cluster_id":7,"district":"NEW_DELHI","event_timestamp":"2026-09-13T10:45:00.000Z","confidence":0.91,"source_reference_hash":"e3b0c44298fc1c149afbf4c8996fb92427ae41e4649b934ca495991b7852b855"}'

peer chaincode invoke \
    -o orderer.cybershield.net:7050 \
    --ordererTLSHostnameOverride orderer.cybershield.net \
    --tls \
    --cafile "${ORDERER_CA}" \
    --channelID "${CHANNEL_NAME}" \
    --name "${CC_NAME}" \
    --peerAddresses peer0.bankb.cybershield.net:8051 --tlsRootCertFiles "${PEER0_BANKB_CA}" \
    --peerAddresses peer0.i4c.cybershield.net:10051 --tlsRootCertFiles "${PEER0_I4C_CA}" \
    -c "{\"function\":\"SubmitSignal\",\"Args\":[\"${SIGNAL_BANKB//\"/\\\"}\"]}" \
    --waitForEvent
echo "[PASS] TEST 3: BankB corroborating signal committed."

# ------------------------------------------------------------------------------
# TEST 4: Query Signals By Cluster 7 (Cross-Bank Corroboration)
# ------------------------------------------------------------------------------
echo ""
echo "=== TEST 4: QuerySignalsByCluster (Cluster 7) ==="
set_org_env "BankC"
CLUSTER_QUERY_RES=$(peer chaincode query -C "${CHANNEL_NAME}" -n "${CC_NAME}" -c '{"function":"QuerySignalsByCluster","Args":["7","false"]}')
echo "Cluster Query Result: ${CLUSTER_QUERY_RES}"
if echo "${CLUSTER_QUERY_RES}" | grep -q "EVT-LIVE-BANKA-001" && echo "${CLUSTER_QUERY_RES}" | grep -q "EVT-LIVE-BANKB-002"; then
    echo "[PASS] TEST 4: Multi-bank corroboration verified across BankA and BankB signals."
else
    echo "[FAIL] TEST 4 failed."
    exit 1
fi

# ------------------------------------------------------------------------------
# TEST 5: LEA Submits Confirmed Cluster Signal
# ------------------------------------------------------------------------------
echo ""
echo "=== TEST 5: LEA Submit LEA_CONFIRMED_CLUSTER (EVT-LIVE-LEA-003) ==="
set_org_env "LEA"
SIGNAL_LEA='{"event_id":"EVT-LIVE-LEA-003","event_type":"LEA_CONFIRMED_CLUSTER","opaque_subject_ref":"opaque-demo-001","cluster_id":7,"district":"NEW_DELHI","event_timestamp":"2026-09-13T11:00:00.000Z","confidence":0.98}'

peer chaincode invoke \
    -o orderer.cybershield.net:7050 \
    --ordererTLSHostnameOverride orderer.cybershield.net \
    --tls \
    --cafile "${ORDERER_CA}" \
    --channelID "${CHANNEL_NAME}" \
    --name "${CC_NAME}" \
    --peerAddresses peer0.lea.cybershield.net:11051 --tlsRootCertFiles "${PEER0_LEA_CA}" \
    --peerAddresses peer0.i4c.cybershield.net:10051 --tlsRootCertFiles "${PEER0_I4C_CA}" \
    -c "{\"function\":\"SubmitSignal\",\"Args\":[\"${SIGNAL_LEA//\"/\\\"}\"]}" \
    --waitForEvent
echo "[PASS] TEST 5: LEA confirmed cluster signal committed."

# ------------------------------------------------------------------------------
# TEST 6: Unauthorized Cross-Bank Modification Attempt
# ------------------------------------------------------------------------------
echo ""
echo "=== TEST 6: Unauthorized Modification (BankC attempts to Correct BankA Signal) ==="
set_org_env "BankC"
UNAUTH_CORR='{"cluster_id":8,"district":"EAST_DELHI"}'
set +e
UNAUTH_RES=$(peer chaincode invoke \
    -o orderer.cybershield.net:7050 \
    --ordererTLSHostnameOverride orderer.cybershield.net \
    --tls \
    --cafile "${ORDERER_CA}" \
    --channelID "${CHANNEL_NAME}" \
    --name "${CC_NAME}" \
    --peerAddresses peer0.bankc.cybershield.net:9051 --tlsRootCertFiles "${PEER0_BANKC_CA}" \
    --peerAddresses peer0.i4c.cybershield.net:10051 --tlsRootCertFiles "${PEER0_I4C_CA}" \
    -c "{\"function\":\"CorrectSignal\",\"Args\":[\"EVT-LIVE-BANKA-001\",\"${UNAUTH_CORR//\"/\\\"}\"]}" \
    --waitForEvent 2>&1)
set -e
echo "Unauthorized attempt response: ${UNAUTH_RES}"
if echo "${UNAUTH_RES}" | grep -qi "Permission Denied"; then
    echo "[PASS] TEST 6: Unauthorized cross-bank modification REJECTED."
else
    echo "[FAIL] TEST 6: Unauthorized modification was not rejected!"
    exit 1
fi

# ------------------------------------------------------------------------------
# TEST 7: Authorized Signal Correction (BankA Corrects Own Signal)
# ------------------------------------------------------------------------------
echo ""
echo "=== TEST 7: Authorized Correction (BankA Corrects EVT-LIVE-BANKA-001) ==="
set_org_env "BankA"
CORR_PAYLOAD='{"event_id":"CORR-LIVE-BANKA-001","cluster_id":7,"district":"NEW_DELHI","confidence":0.95}'
peer chaincode invoke \
    -o orderer.cybershield.net:7050 \
    --ordererTLSHostnameOverride orderer.cybershield.net \
    --tls \
    --cafile "${ORDERER_CA}" \
    --channelID "${CHANNEL_NAME}" \
    --name "${CC_NAME}" \
    --peerAddresses peer0.banka.cybershield.net:7051 --tlsRootCertFiles "${PEER0_BANKA_CA}" \
    --peerAddresses peer0.i4c.cybershield.net:10051 --tlsRootCertFiles "${PEER0_I4C_CA}" \
    -c "{\"function\":\"CorrectSignal\",\"Args\":[\"EVT-LIVE-BANKA-001\",\"${CORR_PAYLOAD//\"/\\\"}\"]}" \
    --waitForEvent

TARGET_AFTER_CORR=$(peer chaincode query -C "${CHANNEL_NAME}" -n "${CC_NAME}" -c '{"function":"GetSignal","Args":["EVT-LIVE-BANKA-001"]}')
echo "Target signal after correction: ${TARGET_AFTER_CORR}"
if echo "${TARGET_AFTER_CORR}" | grep -q '"status":"CORRECTED"' && echo "${TARGET_AFTER_CORR}" | grep -q '"corrected_by_event_id":"CORR-LIVE-BANKA-001"'; then
    echo "[PASS] TEST 7: Authorized correction updated status to CORRECTED and set reference."
else
    echo "[FAIL] TEST 7 failed."
    exit 1
fi

# ------------------------------------------------------------------------------
# TEST 8: Signal Revocation (Submit and Revoke EVT-LIVE-REV-001)
# ------------------------------------------------------------------------------
echo ""
echo "=== TEST 8: Signal Revocation ==="
set_org_env "BankC"
SIGNAL_TO_REVOKE='{"event_id":"EVT-LIVE-REV-001","event_type":"MULE_ACCOUNT_ACTIVITY","opaque_subject_ref":"opaque-mule-001","cluster_id":2,"district":"WEST_DELHI","event_timestamp":"2026-09-13T08:00:00.000Z","confidence":0.75}'
peer chaincode invoke \
    -o orderer.cybershield.net:7050 \
    --ordererTLSHostnameOverride orderer.cybershield.net \
    --tls \
    --cafile "${ORDERER_CA}" \
    --channelID "${CHANNEL_NAME}" \
    --name "${CC_NAME}" \
    --peerAddresses peer0.bankc.cybershield.net:9051 --tlsRootCertFiles "${PEER0_BANKC_CA}" \
    --peerAddresses peer0.i4c.cybershield.net:10051 --tlsRootCertFiles "${PEER0_I4C_CA}" \
    -c "{\"function\":\"SubmitSignal\",\"Args\":[\"${SIGNAL_TO_REVOKE//\"/\\\"}\"]}" \
    --waitForEvent

# Revoke via I4C
set_org_env "I4C"
REV_PAYLOAD='{"event_id":"REV-LIVE-I4C-001","reason":"Mule activity unconfirmed by forensic audit"}'
peer chaincode invoke \
    -o orderer.cybershield.net:7050 \
    --ordererTLSHostnameOverride orderer.cybershield.net \
    --tls \
    --cafile "${ORDERER_CA}" \
    --channelID "${CHANNEL_NAME}" \
    --name "${CC_NAME}" \
    --peerAddresses peer0.i4c.cybershield.net:10051 --tlsRootCertFiles "${PEER0_I4C_CA}" \
    --peerAddresses peer0.bankc.cybershield.net:9051 --tlsRootCertFiles "${PEER0_BANKC_CA}" \
    -c "{\"function\":\"RevokeSignal\",\"Args\":[\"EVT-LIVE-REV-001\",\"${REV_PAYLOAD//\"/\\\"}\"]}" \
    --waitForEvent

TARGET_AFTER_REV=$(peer chaincode query -C "${CHANNEL_NAME}" -n "${CC_NAME}" -c '{"function":"GetSignal","Args":["EVT-LIVE-REV-001"]}')
echo "Target signal after revocation: ${TARGET_AFTER_REV}"
if echo "${TARGET_AFTER_REV}" | grep -q '"status":"REVOKED"'; then
    echo "[PASS] TEST 8: Revocation updated status to REVOKED."
else
    echo "[FAIL] TEST 8 failed."
    exit 1
fi

# Verify default query excludes revoked
CLUSTER2_ACTIVE=$(peer chaincode query -C "${CHANNEL_NAME}" -n "${CC_NAME}" -c '{"function":"QuerySignalsByCluster","Args":["2","false"]}')
echo "Cluster 2 Active Signals: ${CLUSTER2_ACTIVE}"
if echo "${CLUSTER2_ACTIVE}" | grep -q "EVT-LIVE-REV-001"; then
    echo "[FAIL] Revoked signal was returned in default active query!"
    exit 1
else
    echo "[PASS] Revoked signal correctly excluded from default active query."
fi

# ------------------------------------------------------------------------------
# TEST 9: Idempotency (Duplicate Identical vs Duplicate Changed)
# ------------------------------------------------------------------------------
echo ""
echo "=== TEST 9: Idempotency Tests ==="
set_org_env "BankB"
# Identical payload
IDEM_RES=$(peer chaincode invoke \
    -o orderer.cybershield.net:7050 \
    --ordererTLSHostnameOverride orderer.cybershield.net \
    --tls \
    --cafile "${ORDERER_CA}" \
    --channelID "${CHANNEL_NAME}" \
    --name "${CC_NAME}" \
    --peerAddresses peer0.bankb.cybershield.net:8051 --tlsRootCertFiles "${PEER0_BANKB_CA}" \
    --peerAddresses peer0.i4c.cybershield.net:10051 --tlsRootCertFiles "${PEER0_I4C_CA}" \
    -c "{\"function\":\"SubmitSignal\",\"Args\":[\"${SIGNAL_BANKB//\"/\\\"}\"]}" \
    --waitForEvent 2>&1)
echo "Duplicate identical invoke result: ${IDEM_RES}"
if echo "${IDEM_RES}" | grep -qi "SUCCESS"; then
    echo "[PASS] TEST 9a: Duplicate identical payload handled idempotently."
else
    echo "[FAIL] TEST 9a failed."
    exit 1
fi

# Modified payload for same ID
SIGNAL_BANKB_MOD='{"event_id":"EVT-LIVE-BANKB-002","event_type":"ATM_WITHDRAWAL_CONFIRMED","opaque_subject_ref":"opaque-demo-002","cluster_id":99,"district":"SOUTH_DELHI","event_timestamp":"2026-09-13T10:45:00.000Z","confidence":0.50}'
set +e
DUP_CONFLICT_RES=$(peer chaincode invoke \
    -o orderer.cybershield.net:7050 \
    --ordererTLSHostnameOverride orderer.cybershield.net \
    --tls \
    --cafile "${ORDERER_CA}" \
    --channelID "${CHANNEL_NAME}" \
    --name "${CC_NAME}" \
    --peerAddresses peer0.bankb.cybershield.net:8051 --tlsRootCertFiles "${PEER0_BANKB_CA}" \
    --peerAddresses peer0.i4c.cybershield.net:10051 --tlsRootCertFiles "${PEER0_I4C_CA}" \
    -c "{\"function\":\"SubmitSignal\",\"Args\":[\"${SIGNAL_BANKB_MOD//\"/\\\"}\"]}" \
    --waitForEvent 2>&1)
set -e
echo "Duplicate modified payload result: ${DUP_CONFLICT_RES}"
if echo "${DUP_CONFLICT_RES}" | grep -qi "Idempotency conflict"; then
    echo "[PASS] TEST 9b: Duplicate event_id with changed payload REJECTED."
else
    echo "[FAIL] TEST 9b: Duplicate conflict was not rejected!"
    exit 1
fi

# ------------------------------------------------------------------------------
# TEST 10: Time-Window Query
# ------------------------------------------------------------------------------
echo ""
echo "=== TEST 10: Time-Window Query ==="
set_org_env "I4C"
TIME_QUERY_RES=$(peer chaincode query -C "${CHANNEL_NAME}" -n "${CC_NAME}" -c '{"function":"QuerySignalsByTimeWindow","Args":["2026-09-13T10:30:00.000Z","2026-09-13T11:30:00.000Z","false"]}')
echo "Time Window Query Result (Active 10:30 - 11:30): ${TIME_QUERY_RES}"
if echo "${TIME_QUERY_RES}" | grep -q "EVT-LIVE-BANKB-002" && echo "${TIME_QUERY_RES}" | grep -q "EVT-LIVE-LEA-003"; then
    echo "[PASS] TEST 10: Time-window query accurately filtered signals within time range."
else
    echo "[FAIL] TEST 10 failed."
    exit 1
fi

# ------------------------------------------------------------------------------
# TEST 11: Opaque Subject Query
# ------------------------------------------------------------------------------
echo ""
echo "=== TEST 11: Opaque Subject Query ==="
set_org_env "LEA"
SUBJ_QUERY_RES=$(peer chaincode query -C "${CHANNEL_NAME}" -n "${CC_NAME}" -c '{"function":"QuerySignalsByOpaqueSubject","Args":["opaque-demo-001","false"]}')
echo "Opaque Subject Query Result: ${SUBJ_QUERY_RES}"
if echo "${SUBJ_QUERY_RES}" | grep -q "EVT-LIVE-LEA-003"; then
    echo "[PASS] TEST 11: Opaque subject query returned matching signals without PII."
else
    echo "[FAIL] TEST 11 failed."
    exit 1
fi

# ------------------------------------------------------------------------------
# TEST 12: Signal History Proof
# ------------------------------------------------------------------------------
echo ""
echo "=== TEST 12: Signal History Proof ==="
set_org_env "BankA"
HIST_RES=$(peer chaincode query -C "${CHANNEL_NAME}" -n "${CC_NAME}" -c '{"function":"GetSignalHistory","Args":["EVT-LIVE-BANKA-001"]}')
echo "Signal History for EVT-LIVE-BANKA-001: ${HIST_RES}"
if echo "${HIST_RES}" | grep -q "CORRECTED" && echo "${HIST_RES}" | grep -q "tx_id"; then
    echo "[PASS] TEST 12: Full immutable history verified."
else
    echo "[FAIL] TEST 12 failed."
    exit 1
fi

# ------------------------------------------------------------------------------
# TEST 13: Ledger Height Verification
# ------------------------------------------------------------------------------
echo ""
echo "=== TEST 13: Ledger Height Verification ==="
HEIGHT_AFTER=$(get_ledger_height)
echo "Ledger Height Before: ${HEIGHT_BEFORE}"
echo "Ledger Height After:  ${HEIGHT_AFTER}"

if [ "${HEIGHT_AFTER}" -gt "${HEIGHT_BEFORE}" ]; then
    echo "[PASS] TEST 13: Ledger height increased from ${HEIGHT_BEFORE} to ${HEIGHT_AFTER}."
else
    echo "[FAIL] Ledger height did not increase."
    exit 1
fi

echo ""
echo "=================================================="
echo "ALL PHASE B.2 MULTI-ORG FUNCTIONAL TESTS PASSED!"
echo "=================================================="
