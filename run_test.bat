@echo off
setlocal
cd /d "%~dp0"
where py >nul 2>nul
if %errorlevel%==0 (set "PYTHON_CMD=py") else (set "PYTHON_CMD=python")
%PYTHON_CMD% main.py
pause
