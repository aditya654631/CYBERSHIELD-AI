#!/bin/bash
set -euo pipefail

cat << 'EOF' | sudo tee /etc/docker/daemon.json >/dev/null
{
  "features": {
    "containerd-snapshotter": false
  }
}
EOF

sudo systemctl restart docker
sleep 3
sudo chmod 666 /var/run/docker.sock /run/docker.sock 2>/dev/null || true
echo "[OK] Docker configured with standard storage driver."
