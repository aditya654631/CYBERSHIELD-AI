# ==============================================================================
# CyberShield AI — Hyperledger Fabric Network Shutdown (PowerShell)
# ==============================================================================

Write-Host "==================================================" -ForegroundColor Cyan
Write-Host "Shutting Down CyberShield AI Fabric Network" -ForegroundColor Cyan
Write-Host "==================================================" -ForegroundColor Cyan

$scriptDir = Split-Path -Parent $MyInvocation.MyCommand.Path
$networkDir = Split-Path -Parent $scriptDir
$wslPath = (wsl -d Ubuntu -- wslpath -u ($networkDir -replace '\\', '/'))

wsl -d Ubuntu -- bash -lc "cd '$wslPath' && ./scripts/network-down.sh"
