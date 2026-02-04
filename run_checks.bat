@echo off
title Genis Automated Checks
cd /d "%~dp0"
python quick_check.py
if errorlevel 1 (
    echo.
    echo Automated checks failed.
    pause
)
