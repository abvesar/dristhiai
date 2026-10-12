@echo off
title DRISHTI AI - 8-Hour Full Endurance & GNS3 Stability Test
echo ========================================================================
echo       DRISHTI AI -- 8-HOUR FULL ENDURANCE & GNS3 TOPOLOGY TEST
echo ========================================================================
echo [1] Cockpit Operations Hub : http://localhost:5050/
echo [2] Gradio Live AI Hub     : http://localhost:7860/
echo [3] GNS3 Topology Canvas   : DRISTI AI SERVER (127.0.0.1:3080)
echo [4] Duration               : 8.0 Hours (28,800 Seconds)
echo [5] Checkpoint Status      : artifacts\8_hour_test_status.json
echo ========================================================================
echo Launching 8-hour continuous soak test with real-time GNS3 sync...
echo.

if exist ".venv\Scripts\python.exe" (
    ".venv\Scripts\python.exe" run_3hour_endurance_test.py --hours 8.0 --flask-port 5050
) else (
    python run_3hour_endurance_test.py --hours 8.0 --flask-port 5050
)

pause
