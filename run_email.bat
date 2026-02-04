@echo off
title Genis Email Hub
cd /d "%~dp0"
python email_app_v2.py
if errorlevel 1 (
    echo.
    echo Error: Make sure Python is installed and dependencies are available.
    echo Required: pip install msal requests winotify pillow PyMuPDF
    echo Optional (for HTML view): pip install tkinterweb
    echo.
    pause
)
