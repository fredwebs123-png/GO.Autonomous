@echo off
rem Starts the camera program. Extra options pass through, e.g.  start_guidance.bat --source 0
cd /d "%~dp0"
call scripts\pyenv.bat || exit /b 1
"%PY%" run_guidance.py %*
pause
