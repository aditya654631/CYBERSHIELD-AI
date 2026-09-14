#!/bin/bash
# ==============================================================================
# CyberShield AI — Safe Cloud Network Stop (Preserving Volumes)
# NOTE: Does NOT destroy Docker volumes; ledger data remains safe.
# ==============================================================================

set -euo pipefail

SCRIPT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
CLOUD_DIR="$(cd "${SCRIPT_DIR}/.." && pwd)"

cd "${CLOUD_DIR}"

echo "=================================================="
echo "Safely Stopping CyberShield AI Cloud Network"
echo "=================================================="

# Down without -v ensures named volumes (ledger) are 100% preserved
docker compose -f docker-compose.cloud.yml down --remove-orphans

echo "[OK] All cloud Fabric containers stopped cleanly."
echo "[INFO] Persistent ledger volumes are PRESERVED."
echo "=================================================="
