# SDeVPro — Windows'da birinchi marta sozlash (Docker'siz).
# Ishlatish: PowerShell'ni loyiha papkasida oching va shu skriptni ishga tushiring:
#   .\scripts\setup_windows.ps1

$ErrorActionPreference = "Stop"
$root = Split-Path -Parent $PSScriptRoot

Write-Host "== SDeVPro sozlanmoqda ==" -ForegroundColor Cyan

if (-not (Test-Path "$root\.venv")) {
    Write-Host "Virtual environment yaratilmoqda..." -ForegroundColor Yellow
    python -m venv "$root\.venv"
}

$venvPython = "$root\.venv\Scripts\python.exe"

Write-Host "pip yangilanmoqda..." -ForegroundColor Yellow
& $venvPython -m pip install --upgrade pip -q

Write-Host "SDeVPro bog'liqliklari o'rnatilmoqda (Telegram bot dvigateli, Docker talab qilinmaydi)..." -ForegroundColor Yellow
& $venvPython -m pip install -q litellm requests reportlab cryptography python-dotenv dnspython beautifulsoup4 "python-telegram-bot[job-queue]>=21.6"
& $venvPython -m pip install -e "$root" --no-deps -q

if (-not (Test-Path "$root\.env")) {
    Copy-Item "$root\.env.example" "$root\.env"
    Write-Host "'.env' fayli '.env.example' asosida yaratildi. Uni to'ldiring:" -ForegroundColor Green
    Write-Host "  notepad `"$root\.env`"" -ForegroundColor Green
} else {
    Write-Host "'.env' fayli allaqachon mavjud — o'zgartirilmadi." -ForegroundColor DarkGray
}

Write-Host ""
Write-Host "Sozlash tugadi. Keyingi qadamlar:" -ForegroundColor Cyan
Write-Host "  1. .env faylini to'ldiring (kamida TELEGRAM_BOT_TOKEN)"
Write-Host "  2. Botni ishga tushiring: .\scripts\run_bot.ps1"
Write-Host "  3. Botda /start -> /setkey orqali har foydalanuvchi o'z AI tokenini kiritadi"
