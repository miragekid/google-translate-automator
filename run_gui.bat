@echo off
cd /d "%~dp0"
title Google Translate Automator - GUI
echo Menjalankan Google Translate Automator GUI...
if exist "venv\Scripts\python.exe" (
    venv\Scripts\python.exe gui.py
) else (
    python gui.py
)
if %errorlevel% neq 0 (
    echo.
    echo Ada error saat menjalankan GUI.
    pause
)
