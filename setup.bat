@echo off
cd /d "%~dp0"
echo Installing required components (one time only)...
where py >nul 2>nul
if %errorlevel%==0 (
  py -m pip install --upgrade pip
  py -m pip install -r requirements.txt
) else (
  python -m pip install --upgrade pip
  python -m pip install -r requirements.txt
)
echo.
echo Done. Now start the program with run.bat
pause
