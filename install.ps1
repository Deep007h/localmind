# LocalMind Windows Installer (PowerShell)
# Run as Administrator

param(
    [switch]$SkipOllama,
    [switch]$SkipModels
)

$ErrorActionPreference = "Stop"

Write-Host @"

╔═══════════════════════════════════════════════════════════════╗
║                    LocalMind Installer v1.0                  ║
║              Self-Hosted AI Assistant Platform                 ║
╚═══════════════════════════════════════════════════════════════╝

"@ -ForegroundColor Cyan

Write-Host "Checking system requirements..." -ForegroundColor Yellow
$os = Get-CimInstance Win32_OperatingSystem
$ramGB = [math]::Round($os.TotalVisibleMemorySize / 1MB, 0)
Write-Host "RAM: $ramGB GB" -ForegroundColor Gray
if ($ramGB -lt 8) {
    Write-Host "⚠️  Warning: Less than 8GB RAM recommended" -ForegroundColor Yellow
}

$diskFree = (Get-PSDrive C).Free / 1GB
Write-Host "Disk Free: $([math]::Round($diskFree, 0)) GB" -ForegroundColor Gray
if ($diskFree -lt 30) {
    Write-Host "⚠️  Warning: Less than 30GB free disk space" -ForegroundColor Yellow
}

Write-Host "`nChecking Python..." -ForegroundColor Yellow
$pythonCmd = Get-Command python -ErrorAction SilentlyContinue
if (-not $pythonCmd) {
    Write-Host "Installing Python 3.11..." -ForegroundColor Cyan
    $env:PROCESSOR_ARCHITECTURE
    if ($env:PROCESSOR_ARCHITECTURE -eq "AMD64") {
        Invoke-WebRequest -Uri "https://www.python.org/ftp/python/3.11.9/python-3.11.9-amd64.exe" -OutFile "$env:TEMP\python-installer.exe"
        Start-Process -FilePath "$env:TEMP\python-installer.exe" -ArgumentList "/quiet InstallAllUsers=1 PrependPath=1" -Wait
        Remove-Item "$env:TEMP\python-installer.exe" -Force
    } else {
        Write-Host "Error: Python installation not supported on this architecture" -ForegroundColor Red
        exit 1
    }
}

$pythonVersion = python --version 2>&1
Write-Host "Python: $pythonVersion" -ForegroundColor Green

if (-not $SkipOllama) {
    Write-Host "`nChecking Ollama..." -ForegroundColor Yellow
    $ollamaCmd = Get-Command ollama -ErrorAction SilentlyContinue
    if (-not $ollamaCmd) {
        Write-Host "Installing Ollama for Windows..." -ForegroundColor Cyan
        Invoke-WebRequest -Uri "https://ollama.com/download/windows" -OutFile "$env:TEMP\OllamaSetup.exe"
        Start-Process -FilePath "$env:TEMP\OllamaSetup.exe" -ArgumentList "/S" -Wait
        Remove-Item "$env:TEMP\OllamaSetup.exe" -Force
    } else {
        Write-Host "✓ Ollama already installed" -ForegroundColor Green
    }

    Write-Host "Setting OLLAMA_ORIGINS environment variable..." -ForegroundColor Yellow
    [Environment]::SetEnvironmentVariable("OLLAMA_ORIGINS", "*", "Machine")

    Write-Host "Starting Ollama service..." -ForegroundColor Cyan
    Start-Process -FilePath "ollama" -ArgumentList "serve" -WindowStyle Hidden
    Start-Sleep -Seconds 3
}

Write-Host "`nCreating virtual environment..." -ForegroundColor Yellow
python -m venv venv
& ".\venv\Scripts\Activate.ps1"

Write-Host "Installing Python dependencies..." -ForegroundColor Yellow
pip install -r requirements.txt

Write-Host "Creating uploads directory..." -ForegroundColor Yellow
New-Item -ItemType Directory -Path uploads -Force | Out-Null

Write-Host "Creating start script..." -ForegroundColor Yellow
@"
@echo off
call venv\Scripts\activate.bat
start /B uvicorn server:app --host 0.0.0.0 --port 8080
timeout /t 2
start http://localhost:8080
"@ | Out-File -FilePath "start.bat" -Encoding ASCII

if (-not $SkipModels) {
    Write-Host "`n═══════════════════════════════════════════════════════════════" -ForegroundColor Cyan
    Write-Host "                    Pulling AI Models" -ForegroundColor Cyan
    Write-Host "═══════════════════════════════════════════════════════════════`n" -ForegroundColor Cyan

    $models = @("deepseek-r1:8b", "llama3.2-vision:11b", "qwen2.5:7b", "mistral:7b", "nomic-embed-text")

    foreach ($model in $models) {
        Write-Host "Pulling $model..." -ForegroundColor Cyan
        ollama pull $model
    }
}

Write-Host @"

═══════════════════════════════════════════════════════════════
                         ✓ SUCCESS
═══════════════════════════════════════════════════════════════

✅ Ollama running at http://localhost:11434
✅ Models installed: deepseek-r1:8b, llama3.2-vision:11b, qwen2.5:7b, mistral:7b, nomic-embed-text
✅ Server ready at http://localhost:8080

Run 'start.bat' to launch LocalMind anytime.

"@ -ForegroundColor Green

Write-Host "Starting LocalMind..." -ForegroundColor Cyan
Start-Process -FilePath "start.bat"