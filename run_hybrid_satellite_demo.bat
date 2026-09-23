@echo off
title DRISHTI AI - JioSpaceFiber Satellite Failover Demo
echo ========================================================
echo   DRISHTI AI -- JIOSPACEFIBER SATELLITE FAILOVER DEMO
echo ========================================================
echo Instructions:
echo  1. Watch normal cloud telemetry while Wi-Fi is connected.
echo  2. Disconnect Wi-Fi to watch instant failover to JioSpaceFiber.
echo  3. Reconnect Wi-Fi to watch automated store-and-forward sync.
echo ========================================================
if exist ".venv\Scripts\python.exe" (
    ".venv\Scripts\python.exe" fleet_gatekeeper_hub.py --transmission-mode hybrid --distraction-score 0.9 --speed-kph 85 --cycle-seconds 1.0
) else (
    python fleet_gatekeeper_hub.py --transmission-mode hybrid --distraction-score 0.9 --speed-kph 85 --cycle-seconds 1.0
)
pause
