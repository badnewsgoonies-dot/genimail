@echo off
title Genis Email Hub
cd /d "%~dp0"
python email_app_qt.py
if errorlevel 1 (
    echo.
    echo Error: Make sure Python is installed and dependencies are available.
    echo Required: pip install -r requirements.txt
    echo.
    pause
)
