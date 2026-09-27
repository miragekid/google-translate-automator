@echo off
cd /d "%~dp0"
set NODE_OPTIONS=--max-old-space-size=4096
echo Starting Google Translate Automator...
python main.py
pause

