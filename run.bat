@echo off
cd /d "%~dp0"
where pyw >nul 2>nul
if %errorlevel%==0 (
  start "" pyw main.py
) else (
  start "" pythonw main.py
)
