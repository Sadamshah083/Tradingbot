# Sambot package

Your bot runs on the Sambot server; you do not need to host anything for Binance or paper mode.
This download contains the two things that live on your side:

- `mt5_bridge/` - required only for **Exness** (or any MetaTrader 5 broker). Runs on a Windows PC or
  Windows VPS next to your MT5 terminal and lets the Sambot server place, modify and close orders in
  your account. Your MT5 password stays in `config.json` on your machine.
- `data/` - the historical candles behind the backtests on the website (CSV), so you can verify them.

The strategy itself is an invite-only TradingView script. Enter your TradingView username on the
"My bot" page and we add you; the source code is not distributed.

## MT5 bridge in 6 steps

1. Install MetaTrader 5 from Exness and log in (keep it running).
2. Install Python 3.11+ from python.org, ticking "Add Python to PATH".
3. Open a terminal in `mt5_bridge/` and run `pip install -r requirements.txt`.
4. Copy `config.example.json` to `config.json`; fill `login`, `password`, `server` (shown in MT5 under
   Tools -> Options -> Server, e.g. `Exness-MT5Real`) and invent a long random `token`.
5. Run `python bridge.py`. You should see `connected to MT5 account ...` and `bridge listening on ... 5055`.
6. Make it reachable from the internet, then paste the address and token into Sambot -> My bot -> Exness:
   - Windows VPS: use `http://<vps-public-ip>:5055` and allow port 5055 in Windows Firewall.
   - Home PC: forward port 5055 on your router to the PC, or run a free tunnel:
     `cloudflared tunnel --url http://localhost:5055` prints a public https URL to paste.

Symbol names: Exness standard accounts use `XAUUSDm` / `BTCUSDm`; edit `symbols` in `config.json` if your
account shows different names (e.g. `XAUUSD` on Pro/Raw accounts).

Security: the bridge only answers requests carrying your token. Keep the token private; rotate it in both
places if you suspect it leaked. Run the bridge as a normal user, not administrator.
