#!/bin/bash
# ==============================================================================
# CyberShield AI — Cloud VPS Host Bootstrap & Environment Setup
# Target OS: Ubuntu 22.04 / 24.04 LTS
# Installs Docker, Docker Compose, Node.js, UFW Firewall, and Systemd Service
# ==============================================================================

set -euo pipefail

echo "=================================================="
echo "CyberShield AI — Cloud VPS Host Bootstrap Script"
echo "=================================================="

if [ "$(id -u)" -ne 0 ]; then
    echo "[ERROR] This bootstrap script must be run as root or via sudo."
    exit 1
fi

# 1. System Package Updates
echo "--- 1. Updating System Packages ---"
apt-get update -y
apt-get install -y --no-install-recommends \
    apt-transport-https \
    ca-certificates \
    curl \
    gnupg \
    lsb-release \
    jq \
    git \
    ufw \
    tar

# 2. Install Docker & Docker Compose v2 if not installed
if ! command -v docker >/dev/null 2>&1; then
    echo "--- 2. Installing Official Docker Engine & Compose v2 ---"
    install -m 0755 -d /etc/apt/keyrings
    curl -fsSL https://download.docker.com/linux/ubuntu/gpg | gpg --dearmor -o /etc/apt/keyrings/docker.gpg
    chmod a+r /etc/apt/keyrings/docker.gpg

    echo \
      "deb [arch=$(dpkg --print-architecture) signed-by=/etc/apt/keyrings/docker.gpg] https://download.docker.com/linux/ubuntu \
      $(lsb_release -cs) stable" | tee /etc/apt/sources.list.d/docker.list > /dev/null

    apt-get update -y
    apt-get install -y docker-ce docker-ce-cli containerd.io docker-buildx-plugin docker-compose-plugin
    systemctl enable docker
    systemctl start docker
    echo "[OK] Docker installed and started."
else
    echo "--- 2. Docker is already installed: $(docker --version) ---"
fi

# 3. Install Node.js LTS (v18 or v20) for local gateway scripts
if ! command -v node >/dev/null 2>&1; then
    echo "--- 3. Installing Node.js 18 LTS ---"
    curl -fsSL https://deb.nodesource.com/setup_18.x | bash -
    apt-get install -y nodejs
    echo "[OK] Node.js $(node --version) installed."
else
    echo "--- 3. Node.js is already installed: $(node --version) ---"
fi

# 4. Configure Local Hostname Resolution for Consortium
echo "--- 4. Configuring Consortium Local Hostname Resolution ---"
CONSORTIUM_HOSTS="127.0.0.1 orderer.cybershield.net peer0.banka.cybershield.net peer0.bankb.cybershield.net peer0.bankc.cybershield.net peer0.i4c.cybershield.net peer0.lea.cybershield.net gateway.cybershield.net"
if ! grep -q "orderer.cybershield.net" /etc/hosts; then
    echo "${CONSORTIUM_HOSTS}" >> /etc/hosts
    echo "[OK] Consortium hostnames added to /etc/hosts."
else
    echo "[OK] Consortium hostnames already present in /etc/hosts."
fi

# 5. UFW Firewall Configuration
echo "--- 5. Configuring UFW Firewall for Strict Public Isolation ---"
ufw default deny incoming
ufw default allow outgoing
ufw allow 22/tcp comment "SSH Remote Administration"
ufw allow 80/tcp comment "Caddy HTTP ACME Challenge"
ufw allow 443/tcp comment "CyberShield Gateway HTTPS"
# All peer and orderer ports (7050-11052) remain closed to external traffic
ufw --force enable
echo "[OK] UFW firewall active: Only ports 22, 80, and 443 open."

# 6. Secure Crypto File Permissions
SCRIPT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
CLOUD_DIR="$(cd "${SCRIPT_DIR}/.." && pwd)"
BLOCKCHAIN_DIR="$(cd "${CLOUD_DIR}/.." && pwd)"

echo "--- 6. Securing Private Key Permissions (chmod 600) ---"
if [ -d "${BLOCKCHAIN_DIR}/network/organizations" ]; then
    find "${BLOCKCHAIN_DIR}/network/organizations" -type f \( -name "*_sk" -o -name "priv_sk" -o -name "*.key" \) -exec chmod 600 {} +
    echo "[OK] Private keys secured with chmod 600."
fi

# 7. Prepare Secure Backup Directory
mkdir -p /var/backups/cybershield
chmod 700 /var/backups/cybershield
echo "[OK] Secure backup directory initialized at /var/backups/cybershield."

# 8. Install Systemd Auto-Start Service
if [ -f "${CLOUD_DIR}/systemd/cybershield-fabric.service" ]; then
    echo "--- 8. Installing Systemd Service for Reboot Auto-Start ---"
    cp "${CLOUD_DIR}/systemd/cybershield-fabric.service" /etc/systemd/system/
    systemctl daemon-reload
    systemctl enable cybershield-fabric.service
    echo "[OK] cybershield-fabric.service enabled for system boot."
fi

echo "=================================================="
echo "Cloud VPS Host Bootstrap COMPLETED SUCCESSFULLY!"
echo "=================================================="
