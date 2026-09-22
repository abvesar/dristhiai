$ErrorActionPreference = "Stop"

$workspace = Split-Path -Parent $MyInvocation.MyCommand.Path
$python = Join-Path $workspace ".venv\Scripts\python.exe"
$launcher = Join-Path $workspace "launch_all.py"

if (-not (Test-Path $python)) {
    Write-Error "Python venv not found at: $python"
    exit 1
}

Write-Host "Starting DRISHTI AI Dual Dashboards..." -ForegroundColor Green
& $python $launcher
exit $LASTEXITCODE
