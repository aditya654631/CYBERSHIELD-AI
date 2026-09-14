# ==============================================================================
# CyberShield AI — Hyperledger Fabric Health Verification (PowerShell)
# ==============================================================================

$scriptDir = Split-Path -Parent $MyInvocation.MyCommand.Path
$networkDir = Split-Path -Parent $scriptDir
$wslPath = (wsl -d Ubuntu -- wslpath -u ($networkDir -replace '\\', '/'))

wsl -d Ubuntu -- bash -lc "cd '$wslPath' && ./scripts/verify-network.sh"
