# Starts the customer portal on this PC. First run: creates .venv, installs Django, applies migrations.
# Every run: makes SUPERADMIN_EMAIL (from .env) the only admin and rebuilds the downloadable bot package.
param([int]$Port = 8001)
Set-Location $PSScriptRoot
if (-not (Test-Path ".env")) { Copy-Item .env.example .env; Write-Host "Created .env from .env.example - set SUPERADMIN_EMAIL and payment details." -ForegroundColor Yellow }
if (-not (Test-Path ".venv\Scripts\python.exe")) {
    Write-Host "Creating virtual environment and installing Django (first run only)..."
    python -m venv .venv
    .\.venv\Scripts\python.exe -m pip install -q -r requirements.txt
}
$py = ".\.venv\Scripts\python.exe"
& $py manage.py makemigrations accounts signals chat orders --noinput | Out-Null
& $py manage.py migrate --noinput
& $py manage.py ensure_superadmin
& $py manage.py build_package
Write-Host "Portal: http://127.0.0.1:$Port/   (sales page, login, dashboard; admin side only for SUPERADMIN_EMAIL)" -ForegroundColor Green
& $py manage.py runserver 0.0.0.0:$Port --noreload
