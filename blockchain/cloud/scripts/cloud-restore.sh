#!/bin/bash
# ==============================================================================
# CyberShield AI — Cloud Fabric Ledger & Crypto Restore Script
# Restores Named Volumes and Crypto Material from a Backup Archive
# Mode: Supports MIGRATE_EXISTING_LEDGER Workflow
# ==============================================================================

set -euo pipefail

if [ $# -lt 1 ]; then
    echo "Usage: $0 <path-to-cybershield_fabric_backup_*.tar.gz>"
    exit 1
fi

BACKUP_ARCHIVE="$1"
if [ ! -f "${BACKUP_ARCHIVE}" ]; then
    echo "[ERROR] Backup archive not found: ${BACKUP_ARCHIVE}"
    exit 1
fi

SCRIPT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
CLOUD_DIR="$(cd "${SCRIPT_DIR}/.." && pwd)"
BLOCKCHAIN_DIR="$(cd "${CLOUD_DIR}/.." && pwd)"
NETWORK_DIR="${BLOCKCHAIN_DIR}/network"

echo "=================================================="
echo "Starting CyberShield AI Fabric Cloud Restore"
echo "Archive: ${BACKUP_ARCHIVE}"
echo "=================================================="

# 1. Stop active containers first
echo "--- 1. Stopping Active Cloud Containers ---"
cd "${CLOUD_DIR}"
docker compose -f docker-compose.cloud.yml down >/dev/null 2>&1 || true

TEMP_EXTRACT=$(mktemp -d /tmp/cybershield_restore_stage.XXXXXX)
trap 'rm -rf "${TEMP_EXTRACT}"' EXIT

echo "--- 2. Extracting Consolidated Archive ---"
tar -xzf "${BACKUP_ARCHIVE}" -C "${TEMP_EXTRACT}"

# 3. Restore Crypto and Channel Artifacts
echo "--- 3. Restoring Network Crypto Material & Config ---"
if [ -d "${TEMP_EXTRACT}/network/organizations" ]; then
    cp -r "${TEMP_EXTRACT}/network/organizations" "${NETWORK_DIR}/"
    echo "[OK] Organizations crypto restored."
fi

if [ -d "${TEMP_EXTRACT}/network/channel-artifacts" ]; then
    cp -r "${TEMP_EXTRACT}/network/channel-artifacts" "${NETWORK_DIR}/"
    echo "[OK] Channel artifacts restored."
fi

if [ -f "${TEMP_EXTRACT}/cloud.env" ]; then
    cp "${TEMP_EXTRACT}/cloud.env" "${CLOUD_DIR}/.env"
    echo "[OK] Cloud environment restored."
fi

# 4. Restore Named Docker Volumes
echo "--- 4. Restoring Persistent Named Volumes ---"
VOLUMES=(
    "cybershield_orderer_ledger"
    "cybershield_banka_ledger"
    "cybershield_bankb_ledger"
    "cybershield_bankc_ledger"
    "cybershield_i4c_ledger"
    "cybershield_lea_ledger"
)

for vol in "${VOLUMES[@]}"; do
    VOL_TAR="${TEMP_EXTRACT}/volumes/${vol}.tar.gz"
    if [ -f "${VOL_TAR}" ]; then
        echo "Restoring volume: $vol..."
        docker volume create "$vol" >/dev/null
        docker run --rm \
            -v "${vol}:/volume_data" \
            -v "${TEMP_EXTRACT}/volumes:/backup_source:ro" \
            alpine:3.18 \
            sh -c "rm -rf /volume_data/* && tar -xzf /backup_source/${vol}.tar.gz -C /volume_data"
        echo "[OK] Restored $vol."
    else
        echo "[WARN] Backup for volume $vol not present in archive, skipping."
    fi
done

echo "=================================================="
echo "Restore COMPLETED! Starting services..."
docker compose -f docker-compose.cloud.yml up -d
echo "CyberShield AI Cloud Fabric Stack RESTORED & STARTED!"
echo "=================================================="
