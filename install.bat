@echo off
echo.
echo ╔═══════════════════════════════════════════════════════════════╗
echo ║                    LocalMind Installer v1.0                  ║
echo ║              Self-Hosted AI Assistant Platform                 ║
echo ╚═══════════════════════════════════════════════════════════════╝
echo.

where powershell >nul 2>&1
if %errorlevel% neq 0 (
    echo ERROR: PowerShell not found. Please install PowerShell.
    echo Download: https://github.com/PowerShell/PowerShell/releases
    pause
    exit /b 1
)

echo Running LocalMind installer via PowerShell...
echo.

powershell -ExecutionPolicy Bypass -File "%~dp0install.ps1"

if %errorlevel% neq 0 (
    echo.
    echo ERROR: Installation failed. Check install.log for details.
    pause
    exit /b 1
)

echo.
echo Installation complete!
pause