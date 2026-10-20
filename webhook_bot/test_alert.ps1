# Sends a fake "signal" alert to a running bot, exactly like TradingView would.
# Usage:  .\test_alert.ps1 -Url http://YOUR_SERVER_IP/webhook -Secret your-passphrase
param(
    [string]$Url = "http://localhost/webhook",
    [string]$Secret = "change-me-to-a-long-random-string"
)
$body = @{
    event = "signal"; side = "buy"; symbol = "XAUUSD"; exchange = "OANDA"; tf = "60"; strategy = "VWAP Reversal"
    secret = $Secret; price = 4285.5; sl = 4271.2; tp1 = $null; tp2 = 4299.8; qty = 3; id = [string][DateTimeOffset]::UtcNow.ToUnixTimeMilliseconds()
} | ConvertTo-Json -Compress
Invoke-RestMethod -Method Post -Uri $Url -Body $body -ContentType "text/plain"
