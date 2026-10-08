@echo off
rem Finds the project's Python. Order: .venv in the project folder, then the
rem original setup at %USERPROFILE%\venvs\goauto. Sets PY for the caller.
set "PY="
if exist "%~dp0..\.venv\Scripts\python.exe" set "PY=%~dp0..\.venv\Scripts\python.exe"
if not defined PY if exist "%USERPROFILE%\venvs\goauto\Scripts\python.exe" set "PY=%USERPROFILE%\venvs\goauto\Scripts\python.exe"
if not defined PY (
  echo Python environment not found. Double-click setup.bat first.
  pause
  exit /b 1
)
