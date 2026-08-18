# SDeVPro Telegram botini ishga tushirish.
# Doimiy (kompyuter/server qayta yoqilganda ham) ishlashi uchun Windows Task
# Scheduler'da "At startup" trigger bilan shu skriptni chaqiring:
#   Action: powershell.exe
#   Arguments: -NoProfile -ExecutionPolicy Bypass -File "D:\...\SDeVPro\scripts\run_bot.ps1"

$ErrorActionPreference = "Stop"
$root = Split-Path -Parent $PSScriptRoot
$venvPython = "$root\.venv\Scripts\python.exe"

if (-not (Test-Path $venvPython)) {
    Write-Host "Virtual environment topilmadi. Avval ishga tushiring: .\scripts\setup_windows.ps1" -ForegroundColor Red
    exit 1
}

Set-Location $root
& $venvPython -m sdevpro.main
