# ==============================================================================
# CyberShield AI — Hyperledger Fabric Prototype Network Launch (PowerShell)
# Bridges execution directly through Ubuntu WSL2 where Fabric tools are hosted
# ==============================================================================

Write-Host "==================================================" -ForegroundColor Cyan
Write-Host "Starting CyberShield AI Hyperledger Fabric Network" -ForegroundColor Cyan
Write-Host "==================================================" -ForegroundColor Cyan

$scriptDir = Split-Path -Parent $MyInvocation.MyCommand.Path
$networkDir = Split-Path -Parent $scriptDir

# Convert Windows path to WSL path
$wslPath = (wsl -d Ubuntu -- wslpath -u ($networkDir -replace '\\', '/'))

Write-Host "Launching network-up.sh inside Ubuntu WSL2 environment..." -ForegroundColor Yellow
wsl -d Ubuntu -- bash -lc "cd '$wslPath' && ./scripts/network-up.sh"

if ($LASTEXITCODE -eq 0) {
    Write-Host "[OK] Fabric network successfully started." -ForegroundColor Green
} else {
    Write-Host "[FAIL] Network launch failed." -ForegroundColor Red
}
