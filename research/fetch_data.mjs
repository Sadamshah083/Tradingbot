// Re-downloads every dataset in ../data from public endpoints (no API keys): Binance (BTC intraday),
// Bitstamp (BTC daily since 2011), Yahoo Finance (gold futures GC=F).   node fetch_data.mjs
import { writeFileSync, mkdirSync } from 'node:fs';
import { resample } from './lib.mjs';

const out = new URL('../data/', import.meta.url).pathname.replace(/^\/([A-Za-z]:)/, '$1');
mkdirSync(out, { recursive: true });

async function binance(symbol, interval, totalBars) {
  const bars = []; let endTime = Date.now();
  while (bars.length < totalBars) {
    const res = await fetch(`https://api.binance.com/api/v3/klines?symbol=${symbol}&interval=${interval}&limit=1000&endTime=${endTime}`);
    if (!res.ok) throw new Error(`Binance ${res.status}`);
    const rows = await res.json(); if (!rows.length) break;
    bars.unshift(...rows.map(r => ({ time: r[0], open: +r[1], high: +r[2], low: +r[3], close: +r[4], volume: +r[5] })));
    endTime = rows[0][0] - 1; if (rows.length < 1000) break;
    await new Promise(r => setTimeout(r, 150));
  }
  bars.pop(); return bars.slice(-totalBars);
}
async function bitstampDaily() {
  const bars = []; let start = Math.floor(Date.parse('2011-08-18T00:00:00Z') / 1000); const end = Math.floor(Date.now() / 1000);
  while (start < end) {
    const res = await fetch(`https://www.bitstamp.net/api/v2/ohlc/btcusd/?step=86400&limit=1000&start=${start}`);
    if (!res.ok) throw new Error(`Bitstamp ${res.status}`);
    const rows = (await res.json()).data.ohlc; if (!rows.length) break;
    for (const r of rows) bars.push({ time: +r.timestamp * 1000, open: +r.open, high: +r.high, low: +r.low, close: +r.close, volume: +r.volume });
    const last = +rows.at(-1).timestamp; if (last <= start) break; start = last + 86400;
  }
  const seen = new Set(); const uniq = bars.filter(b => !seen.has(b.time) && seen.add(b.time)).sort((a, b) => a.time - b.time); uniq.pop(); return uniq;
}
async function yahoo(ticker, interval, fromSec, toSec) {
  const res = await fetch(`https://query1.finance.yahoo.com/v8/finance/chart/${encodeURIComponent(ticker)}?interval=${interval}&period1=${fromSec}&period2=${toSec}&includePrePost=false`, { headers: { 'User-Agent': 'Mozilla/5.0' } });
  if (!res.ok) throw new Error(`Yahoo ${res.status}`);
  const r = (await res.json()).chart.result[0], q = r.indicators.quote[0], bars = [];
  for (let i = 0; i < r.timestamp.length; i++) {
    if ([q.open[i], q.high[i], q.low[i], q.close[i]].some(v => v == null)) continue;
    bars.push({ time: r.timestamp[i] * 1000, open: q.open[i], high: q.high[i], low: q.low[i], close: q.close[i], volume: q.volume[i] ?? 0 });
  }
  return bars;
}
function save(name, bars) {
  const csv = ['time_utc,timestamp_ms,open,high,low,close,volume', ...bars.map(b => `${new Date(b.time).toISOString()},${b.time},${b.open},${b.high},${b.low},${b.close},${b.volume}`)];
  writeFileSync(`${out}${name}.csv`, csv.join('\n') + '\n');
  console.log(`${name}.csv`.padEnd(14), String(bars.length).padStart(6), 'bars', new Date(bars[0].time).toISOString().slice(0, 10), '->', new Date(bars.at(-1).time).toISOString().slice(0, 10));
}
const now = Math.floor(Date.now() / 1000), day = 86400;
save('btc_5m', await binance('BTCUSDT', '5m', 52000));
save('btc_15m', await binance('BTCUSDT', '15m', 35000));
const btc1h = await binance('BTCUSDT', '1h', 8760); save('btc_1h', btc1h); save('btc_4h', resample(btc1h, 4));
save('btc_1d', await bitstampDaily());
save('gold_5m', await yahoo('GC=F', '5m', now - 59 * day, now));
save('gold_15m', await yahoo('GC=F', '15m', now - 59 * day, now));
const gold1h = await yahoo('GC=F', '1h', now - 729 * day, now); save('gold_1h', gold1h); save('gold_4h', resample(gold1h, 4));
save('gold_1d', await yahoo('GC=F', '1d', Math.floor(Date.parse('2000-01-01T00:00:00Z') / 1000), now));
