# Starts the webhook bot on this PC (paper mode unless .env says otherwise).
# First run creates .venv and installs the requirements. Keep this window open while trading.
param([int]$Port = 8000)
Set-Location $PSScriptRoot
if (-not (Test-Path ".env")) { Write-Host "No .env found - copy .env.example to .env and set WEBHOOK_SECRET first." -ForegroundColor Red; exit 1 }
if (-not (Test-Path ".venv\Scripts\python.exe")) {
    Write-Host "Creating virtual environment and installing requirements (first run only)..."
    python -m venv .venv
    .\.venv\Scripts\python.exe -m pip install -q -r requirements.txt
}
Write-Host "Bot listening on http://127.0.0.1:$Port  (health: http://127.0.0.1:$Port/health)"
.\.venv\Scripts\python.exe -m uvicorn server:app --host 127.0.0.1 --port $Port --proxy-headers
