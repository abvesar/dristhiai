@echo off
title DRISHTI AI - 3-Hour Endurance & Continuous Stability Test
echo ========================================================================
echo       DRISHTI AI -- 3-HOUR ENDURANCE TEST WITH LIVE BROWSER DASHBOARD
echo ========================================================================
echo [1] Cockpit Operations Hub: http://localhost:5000/
echo [2] Gradio Live AI Hub    : http://localhost:7860/
echo [3] Duration              : 3.0 Hours (10,800 Seconds)
echo [4] Telemetry Checkpoint  : artifacts\3_hour_test_status.json
echo ========================================================================
echo Launching test suite and opening dashboards in default browser...
echo.

if exist ".venv\Scripts\python.exe" (
    ".venv\Scripts\python.exe" run_3hour_endurance_test.py --hours 3.0
) else (
    python run_3hour_endurance_test.py --hours 3.0
)

pause
