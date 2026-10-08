@echo off
rem One-time setup on a new PC. Double-click it, or run it from PowerShell.
rem Needs Python 3.11+ installed (python.org, tick "Add python.exe to PATH").
cd /d "%~dp0"
where python >nul 2>nul || (echo Python not found. Install it from python.org first, then rerun. & pause & exit /b 1)
if not exist .venv (
  echo Creating .venv ...
  python -m venv .venv || (pause & exit /b 1)
)
set "PY=%~dp0.venv\Scripts\python.exe"
"%PY%" -m pip install --upgrade pip
rem CPU PyTorch works everywhere. For an NVIDIA training PC, see README "GPU".
"%PY%" -m pip install torch torchvision --index-url https://download.pytorch.org/whl/cpu || (pause & exit /b 1)
"%PY%" -m pip install -r requirements.txt || (pause & exit /b 1)
echo.
echo Running tests...
"%PY%" -m pytest tests -q -p no:cacheprovider
echo.
echo Setup done. Next: start_avatar.bat and start_guidance.bat (see START_HERE.md).
pause
