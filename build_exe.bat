@echo off
cd /d "%~dp0"
echo ============================================
echo  Building DotaBetTracker.exe (a few minutes)
echo ============================================
where py >nul 2>nul
if %errorlevel%==0 (set PY=py) else (set PY=python)
if not exist assets\icon.ico %PY% tools\make_icon.py
%PY% -m PyInstaller --noconfirm --clean --windowed --name DotaBetTracker --icon assets\icon.ico --add-data "assets;assets" --collect-submodules openpyxl main.py
if errorlevel 1 (
  echo.
  echo BUILD FAILED. Check the messages above.
  pause
  exit /b 1
)
%PY% tools\write_installer_version.py
echo.
echo Done! Program folder: dist\DotaBetTracker  (start DotaBetTracker.exe)
echo To make a desktop shortcut run: create_shortcut.bat
pause
