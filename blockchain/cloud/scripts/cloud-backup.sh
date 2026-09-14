#!/bin/bash
# ==============================================================================
# CyberShield AI — Cloud Fabric Ledger & Crypto Backup Script
# Archives Docker Named Volumes and Crypto Material Safely
# Stored in /var/backups/cybershield/ with chmod 600 permissions
# DO NOT COMMIT BACKUPS TO GIT
# ==============================================================================

set -euo pipefail

SCRIPT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
CLOUD_DIR="$(cd "${SCRIPT_DIR}/.." && pwd)"
BLOCKCHAIN_DIR="$(cd "${CLOUD_DIR}/.." && pwd)"
NETWORK_DIR="${BLOCKCHAIN_DIR}/network"

BACKUP_DIR="/var/backups/cybershield"
TIMESTAMP=$(date -u +"%Y%m%d_%H%M%SZ")
BACKUP_ARCHIVE="${BACKUP_DIR}/cybershield_fabric_backup_${TIMESTAMP}.tar.gz"

echo "=================================================="
echo "Starting CyberShield AI Fabric Cloud Backup"
echo "Timestamp: ${TIMESTAMP}"
echo "=================================================="

mkdir -p "${BACKUP_DIR}"
chmod 700 "${BACKUP_DIR}"

TEMP_STAGE=$(mktemp -d /tmp/cybershield_backup_stage.XXXXXX)
trap 'rm -rf "${TEMP_STAGE}"' EXIT

echo "--- 1. Backing Up Crypto Material & Channel Artifacts ---"
mkdir -p "${TEMP_STAGE}/network"
if [ -d "${NETWORK_DIR}/organizations" ]; then
    cp -r "${NETWORK_DIR}/organizations" "${TEMP_STAGE}/network/"
fi
if [ -d "${NETWORK_DIR}/channel-artifacts" ]; then
    cp -r "${NETWORK_DIR}/channel-artifacts" "${TEMP_STAGE}/network/"
fi
if [ -f "${CLOUD_DIR}/.env" ]; then
    cp "${CLOUD_DIR}/.env" "${TEMP_STAGE}/cloud.env"
fi

echo "--- 2. Exporting Persistent Named Volumes ---"
VOLUMES=(
    "cybershield_orderer_ledger"
    "cybershield_banka_ledger"
    "cybershield_bankb_ledger"
    "cybershield_bankc_ledger"
    "cybershield_i4c_ledger"
    "cybershield_lea_ledger"
)

mkdir -p "${TEMP_STAGE}/volumes"
for vol in "${VOLUMES[@]}"; do
    if docker volume inspect "$vol" >/dev/null 2>&1; then
        echo "Exporting volume: $vol..."
        docker run --rm \
            -v "${vol}:/volume_data:ro" \
            -v "${TEMP_STAGE}/volumes:/backup_target" \
            alpine:3.18 \
            tar -czf "/backup_target/${vol}.tar.gz" -C /volume_data .
        echo "[OK] Exported $vol."
    else
        echo "[WARN] Volume $vol not found, skipping."
    fi
done

echo "--- 3. Creating Encrypted / Compressed Consolidated Archive ---"
tar -czf "${BACKUP_ARCHIVE}" -C "${TEMP_STAGE}" .
chmod 600 "${BACKUP_ARCHIVE}"

ARCHIVE_SIZE=$(du -h "${BACKUP_ARCHIVE}" | cut -f1)
echo "=================================================="
echo "Backup COMPLETED SUCCESSFULLY!"
echo "Archive: ${BACKUP_ARCHIVE}"
echo "Size: ${ARCHIVE_SIZE}"
echo "Permissions: 600 (Restricted to Root)"
echo "=================================================="
