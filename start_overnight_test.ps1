$ErrorActionPreference = "Stop"

$workspace = Split-Path -Parent $MyInvocation.MyCommand.Path
$python = Join-Path $workspace ".venv\Scripts\python.exe"
$suite = Join-Path $workspace "tests\overnight_endurance_suite.py"

if (-not (Test-Path $python)) {
    Write-Error "Python virtual environment not found at: $python"
    exit 1
}

Write-Host "==========================================================" -ForegroundColor Cyan
Write-Host "   DRISHTI AI -- LAUNCHING 8-HOUR OVERNIGHT SOAK TEST" -ForegroundColor Cyan
Write-Host "==========================================================" -ForegroundColor Cyan
Write-Host " [x] Windows Sleep Prevention: Active (ES_SYSTEM_REQUIRED)"
Write-Host " [x] Adversarial Frame Injection: Active"
Write-Host " [x] Live Report Path: artifacts\soak_tests\OVERNIGHT_REPORT.md"
Write-Host "==========================================================" -ForegroundColor Cyan

# Default to 8.0 hours; user can pass arguments if desired
$duration = if ($args.Count -gt 0) { $args[0] } else { "8.0" }

$env:PYTHONUNBUFFERED = "1"
& $python $suite --duration-hours $duration
exit $LASTEXITCODE
