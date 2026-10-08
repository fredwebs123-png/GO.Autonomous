@echo off
rem Runs any project script with the project's Python, e.g.
rem   run_tool.bat find_cameras.py
rem   run_tool.bat calibrate.py --source 1
rem   run_tool.bat set_search_area.py
cd /d "%~dp0"
call scripts\pyenv.bat || exit /b 1
"%PY%" %*
