@echo off
title Genis Email Hub
cd /d "%~dp0"
python email_app_qt.py
set EC=%errorlevel%
if %EC% neq 0 (
    echo.
    echo === APP CRASHED (exit code %EC%) ===
    echo.
    if exist crash_log.txt (
        type crash_log.txt
        echo.
        echo --- Crash log saved to crash_log.txt ---
    )
    echo.
    pause
)
