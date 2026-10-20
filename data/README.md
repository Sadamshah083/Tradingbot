# Market data

OHLCV candles used to test the strategies. Columns: `time_utc, timestamp_ms, open, high, low, close, volume`. All times are UTC.

| file | what | rows | from | to |
| --- | --- | --- | --- | --- |
| btc_15m.csv | BTCUSDT 15-minute, Binance spot | 34999 | 2025-09-29 | 2026-09-28 |
| btc_1d.csv | BTCUSD daily, Bitstamp (full exchange history) | 5517 | 2011-08-18 | 2026-09-24 |
| btc_1h.csv | BTCUSDT 1-hour, Binance spot | 8760 | 2025-09-25 | 2026-09-25 |
| btc_4h.csv | BTCUSDT 4-hour, built from the 1-hour bars | 2191 | 2025-09-25 | 2026-09-25 |
| btc_5m.csv | BTCUSDT 5-minute, Binance spot | 51999 | 2026-04-01 | 2026-09-28 |
| gold_15m.csv | Gold futures GC=F 15-minute, Yahoo Finance | 4528 | 2026-07-20 | 2026-09-28 |
| gold_1d.csv | Gold futures GC=F daily, Yahoo Finance | 6543 | 2000-08-30 | 2026-09-25 |
| gold_1h.csv | Gold futures GC=F 1-hour, Yahoo Finance | 13767 | 2024-05-03 | 2026-09-25 |
| gold_4h.csv | Gold futures GC=F 4-hour, built from the 1-hour bars | 3724 | 2024-05-03 | 2026-09-25 |
| gold_5m.csv | Gold futures GC=F 5-minute, Yahoo Finance | 13551 | 2026-07-20 | 2026-09-28 |

Notes

- Bitcoin has traded since 2010; the Bitstamp daily file is the complete exchange history that exists (15 years). There is no 16- or 20-year BTC history anywhere.
- Gold daily covers 26 years (2000-2026). Yahoo limits intraday history: 1-hour bars to ~2 years, 5/15-minute bars to 60 days.
- Refresh everything with `node research/fetch_data.mjs` (needs internet; Binance, Bitstamp and Yahoo public endpoints, no keys).
- Gold futures (GC=F) differ slightly from spot XAUUSD at your broker (roughly a few dollars of basis and different session hours); use them for research, not for exact price matching.
