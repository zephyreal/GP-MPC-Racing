@echo off
chcp 65001 >nul
cd /d "%~dp0"
where py >nul 2>nul
if errorlevel 1 goto use_python
py -3.12 launch.py
goto finished
:use_python
python launch.py
:finished
if errorlevel 1 echo Install Python 3.12 with Add Python to PATH, then retry.
pause
