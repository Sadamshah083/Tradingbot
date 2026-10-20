# Opens a free public HTTPS tunnel to the bot running on this PC so TradingView can reach it.
# Default: SSH reverse tunnel via localhost.run (no account, uses Windows' built-in ssh.exe).
# Alternative: -Method cloudflare (blocked on some networks).
# Prints the public URL to paste into the TradingView alert (add /webhook). The URL changes every restart.
param([int]$Port = 8000, [ValidateSet("ssh", "cloudflare")][string]$Method = "ssh")
Set-Location $PSScriptRoot
if ($Method -eq "cloudflare") {
    $exe = Join-Path $PSScriptRoot "tools\cloudflared.exe"
    if (-not (Test-Path $exe)) {
        New-Item -ItemType Directory -Force -Path (Split-Path $exe) | Out-Null
        Write-Host "Downloading cloudflared..."
        Invoke-WebRequest -Uri "https://github.com/cloudflare/cloudflared/releases/latest/download/cloudflared-windows-amd64.exe" -OutFile $exe
    }
    Write-Host "Starting Cloudflare tunnel to http://127.0.0.1:$Port - look for the https://....trycloudflare.com line."
    & $exe tunnel --url "http://127.0.0.1:$Port" --no-autoupdate
} else {
    Write-Host "Starting SSH tunnel to http://127.0.0.1:$Port via localhost.run ..."
    Write-Host "Keep this window open. The tunnel reconnects by itself if the relay drops; a NEW URL is printed each time,"
    Write-Host "and the TradingView alert must then be updated with it."
    New-Item -ItemType Directory -Force -Path (Join-Path $PSScriptRoot "logs") | Out-Null
    $urlFile = Join-Path $PSScriptRoot "logs\public_url.txt"
    while ($true) {
        ssh -T -o StrictHostKeyChecking=no -o UserKnownHostsFile=NUL -o ServerAliveInterval=20 -o ServerAliveCountMax=3 -o ExitOnForwardFailure=yes -R "80:127.0.0.1:$Port" nokey@localhost.run 2>&1 | ForEach-Object {
            $line = "$_"
            if ($line -match 'https://[a-z0-9-]+\.lhr\.life') {
                Set-Content -Path $urlFile -Value $matches[0]
                Write-Host ""
                Write-Host ("PUBLIC WEBHOOK URL:  " + $matches[0] + "/webhook   (" + (Get-Date -Format 'HH:mm:ss') + ")") -ForegroundColor Green
                Write-Host "(also saved to logs\public_url.txt)"
                Write-Host ""
            }
            $line
        }
        # Reconnecting too fast makes the relay close each new session immediately (throttling), so wait.
        Write-Host ("Tunnel dropped at " + (Get-Date -Format 'HH:mm:ss') + " - reconnecting in 30 s ...") -ForegroundColor Yellow
        Start-Sleep -Seconds 30
    }
}
