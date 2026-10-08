@echo off
rem Starts the Miles screen server, then open http://localhost:8000 in Chrome.
rem Add --demo to cycle through every signal without the camera.
cd /d "%~dp0"
call scripts\pyenv.bat || exit /b 1
"%PY%" avatar_server.py %*
pause
