@echo off
setlocal
cd /d "%~dp0"

where py >nul 2>nul
if errorlevel 1 (
    echo [ERROR] Python launcher not found. Install Python 3.12 first.
    goto :failed
)

if not exist ".venv-win\Scripts\python.exe" (
    py -3.12 -m venv .venv-win
    if errorlevel 1 goto :failed
)

call .venv-win\Scripts\activate.bat
python -m pip install --upgrade pip
if errorlevel 1 goto :failed

python -m pip install -e ".[dev,build]"
if errorlevel 1 goto :failed

python -m pytest
if errorlevel 1 goto :failed

python -m PyInstaller --noconfirm --clean packaging\script2gif.spec
if errorlevel 1 goto :failed

if exist "C:\Program Files (x86)\Inno Setup 6\ISCC.exe" (
    "C:\Program Files (x86)\Inno Setup 6\ISCC.exe" packaging\installer.iss
    if errorlevel 1 goto :failed
)

echo.
echo Build completed: dist\Script2Gif\Script2Gif.exe
echo Installer (when Inno Setup is installed): dist\installer\Script2Gif-Setup-0.2.0.exe
echo Run verify_windows.ps1 to perform the executable smoke test.
pause
endlocal
exit /b 0

:failed
echo.
echo [ERROR] Build failed. Review the messages above.
pause
endlocal
exit /b 1
