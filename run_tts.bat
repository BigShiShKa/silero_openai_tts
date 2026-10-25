@echo off
chcp 65001 >nul
cd /d "%~dp0"
"%~dp0.venv\Scripts\python.exe" "%~dp0run_tts.py" %*
set "TTS_EXIT_CODE=%ERRORLEVEL%"
if not "%TTS_EXIT_CODE%"=="0" pause
exit /b %TTS_EXIT_CODE%
