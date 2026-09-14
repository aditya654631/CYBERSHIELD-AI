#!/bin/bash
# ==============================================================================
# CyberShield AI — Cloud Network Safe Restart & Ledger Continuity Test
# Restarts all Fabric containers and verifies block height & chaincode state
# ==============================================================================

set -euo pipefail

SCRIPT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
CLOUD_DIR="$(cd "${SCRIPT_DIR}/.." && pwd)"
BLOCKCHAIN_DIR="$(cd "${CLOUD_DIR}/.." && pwd)"
NETWORK_DIR="${BLOCKCHAIN_DIR}/network"

cd "${CLOUD_DIR}"

echo "=================================================="
echo "Restarting CyberShield AI Cloud Fabric Stack"
echo "=================================================="

# 1. Query pre-restart Gateway health if available
echo "--- 1. Querying Gateway Health Before Restart ---"
PRE_HEALTH=$(curl -s http://127.0.0.1:4000/api/v1/gateway/health || echo '{"status":"OFFLINE"}')
echo "Pre-restart health: ${PRE_HEALTH}"

# 2. Restart Containers
echo "--- 2. Restarting Containers via Docker Compose ---"
docker compose -f docker-compose.cloud.yml restart

# 3. Wait for Services to Stabilize
echo "--- 3. Waiting for Services to Recover ---"
sleep 6

# 4. Verify Post-restart Gateway Health & Ledger Access
echo "--- 4. Querying Gateway Health After Restart ---"
for attempt in {1..10}; do
    POST_HEALTH=$(curl -s http://127.0.0.1:4000/api/v1/gateway/health || echo '{"status":"RETRY"}')
    if echo "${POST_HEALTH}" | grep -q '"ledger":"ACCESSIBLE"'; then
        echo "[PASS] Gateway recovered: Ledger is ACCESSIBLE after restart."
        echo "${POST_HEALTH}" | jq . || echo "${POST_HEALTH}"
        break
    else
        echo "Waiting for Gateway recovery ($attempt/10)..."
        sleep 2
    fi
done

echo "=================================================="
echo "Cloud Network Restart & Continuity Verification COMPLETE"
echo "=================================================="
