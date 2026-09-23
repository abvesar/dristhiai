@echo off
title DRISHTI AI - Test Suite Runner
echo ========================================================
echo       DRISHTI AI -- VERIFYING TEST SUITE
echo ========================================================
if exist ".venv\Scripts\python.exe" (
    ".venv\Scripts\python.exe" -m unittest discover tests
) else (
    python -m unittest discover tests
)
echo ========================================================
pause
