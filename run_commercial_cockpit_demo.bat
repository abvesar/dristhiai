@echo off
title DRISHTI AI - Commercial Vehicle Cockpit & Dual-Screen Showcase
echo ========================================================================
echo       DRISHTI AI -- COMMERCIAL VEHICLE CAB & DUAL-SCREEN SHOWCASE
echo ========================================================================
echo [1] Screen 1 (Laptop): Commercial Truck Cockpit (Gauges, DMS, Audio)
echo [2] Screen 2 (Phone) : Fleet Operations Control Room (Scan QR Code)
echo ========================================================================
if exist ".venv\Scripts\python.exe" (
    ".venv\Scripts\python.exe" launch_cockpit_showcase.py
) else (
    python launch_cockpit_showcase.py
)
pause
