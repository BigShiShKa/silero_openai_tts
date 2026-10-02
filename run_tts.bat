@echo off
chcp 65001 >nul
cd /d "%~dp0"
"%~dp0.venv\Scripts\python.exe" "%~dp0run_tts.py" %*
if errorlevel 1 pause