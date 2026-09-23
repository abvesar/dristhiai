@echo off
title DRISHTI AI - Dual Dashboards Launcher
echo ========================================================
echo       DRISHTI AI -- LAUNCHING DUAL DASHBOARDS
echo ========================================================
echo [1] Flask Operations Command: http://localhost:5000/
echo [2] Gradio AI Telemetry Hub : http://localhost:7860/
echo ========================================================
if exist ".venv\Scripts\python.exe" (
    ".venv\Scripts\python.exe" launch_all.py
) else (
    python launch_all.py
)
pause
