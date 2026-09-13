#!/bin/bash
# ==============================================================================
# CyberShield AI — Hyperledger Fabric Network Shutdown
# ==============================================================================

set -euo pipefail

SCRIPT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
NETWORK_DIR="$(cd "${SCRIPT_DIR}/.." && pwd)"

cd "${NETWORK_DIR}"

echo "=================================================="
echo "Shutting Down CyberShield AI Fabric Network"
echo "=================================================="

docker compose down --volumes --remove-orphans

echo "[OK] All Fabric containers, volumes, and networks stopped."
echo "[INFO] PostgreSQL database and ML artifacts remain untouched."
