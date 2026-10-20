/**
 * Gold & BTC Strategy Lab — trend-filtered RSI pullback.
 *
 * Instruments (exact; do not mix):
 *   Gold → XAUUSD research proxy = Yahoo GC=F continuous futures (NOT GLD ETF)
 *   BTC  → BTC/USD spot (Bitstamp daily ending ~00:00 UTC)
 *
 * These are proposed test settings, not a guaranteed edge.
 * Run: node pullback_lab.mjs [--write]
 */
import { writeFileSync, readFileSync } from 'node:fs';
import { fileURLToPath } from 'node:url';
import { dirname, join } from 'node:path';
import { loadCsv } from './lib.mjs';

const ROOT = join(dirname(fileURLToPath(import.meta.url)), '..');

function sma(closes, period, i) {
  if (i + 1 < period) return NaN;
  let s = 0;
  for (let k = i - period + 1; k <= i; k++) s += closes[k];
  return s / period;
}

/** Wilder-style RSI on close; period typically 2. */
function rsiSeries(closes, period) {
  const out = new Array(closes.length).fill(NaN);
  if (closes.length < period + 1) return out;
  let avgGain = 0, avgLoss = 0;
  for (let i = 1; i <= period; i++) {
    const d = closes[i] - closes[i - 1];
    if (d >= 0) avgGain += d; else avgLoss -= d;
  }
  avgGain /= period; avgLoss /= period;
  out[period] = avgLoss === 0 ? 100 : 100 - 100 / (1 + avgGain / avgLoss);
  for (let i = period + 1; i < closes.length; i++) {
    const d = closes[i] - closes[i - 1];
    const gain = d > 0 ? d : 0, loss = d < 0 ? -d : 0;
    avgGain = (avgGain * (period - 1) + gain) / period;
    avgLoss = (avgLoss * (period - 1) + loss) / period;
    out[i] = avgLoss === 0 ? 100 : 100 - 100 / (1 + avgGain / avgLoss);
  }
  return out;
}

function atrSeries(bars, period) {
  const out = new Array(bars.length).fill(NaN);
  const tr = bars.map((b, i) => {
    if (i === 0) return b.high - b.low;
    const prev = bars[i - 1].close;
    return Math.max(b.high - b.low, Math.abs(b.high - prev), Math.abs(b.low - prev));
  });
  let sum = 0;
  for (let i = 0; i < bars.length; i++) {
    if (i < period) { sum += tr[i]; if (i === period - 1) out[i] = sum / period; continue; }
    out[i] = (out[i - 1] * (period - 1) + tr[i]) / period;
  }
  return out;
}

function iso(ms) { return new Date(ms).toISOString().slice(0, 10); }

/**
 * Long-only pullback backtest.
 * Signal on completed bar i → entry at open of i+1.
 */
function backtest(bars, cfg) {
  const closes = bars.map(b => b.close);
  const rsi = rsiSeries(closes, cfg.rsiPeriod);
  const atr = atrSeries(bars, cfg.atrPeriod);
  const trades = [];
  let pos = null; // { entryBar, entryPrice, stop, reason }

  const costPerSide = cfg.costPct / 100; // applied on entry and exit as fraction of price

  for (let i = 0; i < bars.length - 1; i++) {
    const c = closes[i];
    const sma200 = sma(closes, 200, i);
    const r = rsi[i];
    const a = atr[i];
    if (!Number.isFinite(sma200) || !Number.isFinite(r)) continue;

    // Manage open position using completed bar i
    if (pos) {
      const barsHeld = i - pos.entryBar + 1; // entry filled on entryBar open; evaluating at close of i
      let exitPrice = null, why = null;

      // Stop hit during bar (conservative: if low <= stop, fill at stop; gaps open below stop → open)
      if (Number.isFinite(pos.stop)) {
        if (bars[i].open <= pos.stop) { exitPrice = bars[i].open; why = 'stop_gap'; }
        else if (bars[i].low <= pos.stop) { exitPrice = pos.stop; why = 'stop'; }
      }

      if (!exitPrice && c < sma200) { exitPrice = c; why = 'trend_exit'; }
      if (!exitPrice && r > cfg.rsiExit) { exitPrice = c; why = 'rsi_exit'; }
      if (!exitPrice && barsHeld >= cfg.maxBars) { exitPrice = c; why = 'time_exit'; }

      if (exitPrice != null) {
        const entry = pos.entryPrice * (1 + costPerSide);
        const exit = exitPrice * (1 - costPerSide);
        const profit = (exit - entry) * cfg.qty;
        trades.push({
          entry: iso(bars[pos.entryBar].time),
          exit: iso(bars[i].time),
          side: 'long',
          entry_price: +entry.toFixed(4),
          exit_price: +exit.toFixed(4),
          profit: +profit.toFixed(2),
          reason_entry: pos.reason,
          reason_exit: why,
          bars: barsHeld,
        });
        pos = null;
      }
    }

    // New signal on completed bar i (only if flat)
    if (!pos) {
      const inTrend = c > sma200 && (cfg.requireMomentum30 ? c > closes[i - 30] : true);
      const setup = r < cfg.rsiEntry;
      if (inTrend && setup && i + 1 < bars.length && Number.isFinite(a)) {
        const entryBar = i + 1;
        const rawEntry = bars[entryBar].open;
        const stop = rawEntry - cfg.atrStopMult * a;
        pos = { entryBar, entryPrice: rawEntry, stop, reason: `rsi${cfg.rsiPeriod}<${cfg.rsiEntry} + sma200` };
      }
    }
  }

  // Force flat at end
  if (pos) {
    const i = bars.length - 1;
    const entry = pos.entryPrice * (1 + costPerSide);
    const exit = bars[i].close * (1 - costPerSide);
    trades.push({
      entry: iso(bars[pos.entryBar].time),
      exit: iso(bars[i].time),
      side: 'long',
      entry_price: +entry.toFixed(4),
      exit_price: +exit.toFixed(4),
      profit: +((exit - entry) * cfg.qty).toFixed(2),
      reason_entry: pos.reason,
      reason_exit: 'eod',
      bars: i - pos.entryBar + 1,
    });
  }

  return summarize(trades, bars, cfg);
}

function summarize(trades, bars, cfg) {
  const n = trades.length;
  const wins = trades.filter(t => t.profit > 0);
  const losses = trades.filter(t => t.profit <= 0);
  const gp = wins.reduce((a, t) => a + t.profit, 0);
  const gl = losses.reduce((a, t) => a + t.profit, 0);
  let equity = 0, peak = 0, maxDd = 0, maxDdPct = 0;
  const equityCurve = [];
  let streak = 0, maxStreak = 0;
  for (const t of trades) {
    equity += t.profit;
    peak = Math.max(peak, equity);
    const dd = peak - equity;
    maxDd = Math.max(maxDd, dd);
    maxDdPct = Math.max(maxDdPct, cfg.initialCapital ? (dd / cfg.initialCapital) * 100 : 0);
    equityCurve.push([t.exit, +equity.toFixed(2)]);
    if (t.profit <= 0) { streak++; maxStreak = Math.max(maxStreak, streak); }
    else streak = 0;
  }
  const first = bars[0], last = bars[bars.length - 1];
  const bh = ((last.close / first.close) - 1) * 100;
  return {
    trades: n,
    win_rate: n ? +(100 * wins.length / n).toFixed(1) : 0,
    profit_factor: gl !== 0 ? +(gp / Math.abs(gl)).toFixed(2) : (gp > 0 ? 999 : 0),
    net: +equity.toFixed(2),
    net_pct: +((equity / cfg.initialCapital) * 100).toFixed(1),
    avg_win: wins.length ? +(gp / wins.length).toFixed(2) : 0,
    avg_loss: losses.length ? +(gl / losses.length).toFixed(2) : 0,
    max_drawdown_pct: +maxDdPct.toFixed(1),
    max_consecutive_losses: maxStreak,
    winning_trades: wins.length,
    losing_trades: losses.length,
    largest_win: wins.length ? +Math.max(...wins.map(t => t.profit)).toFixed(2) : 0,
    largest_loss: losses.length ? +Math.min(...losses.map(t => t.profit)).toFixed(2) : 0,
    buy_hold_pct: +bh.toFixed(1),
    avg_bars: n ? +(trades.reduce((a, t) => a + t.bars, 0) / n).toFixed(1) : 0,
    equity: equityCurve,
    trades_list: trades,
    start: iso(first.time),
    end: iso(last.time),
    bars: bars.length,
  };
}

function sliceByDate(bars, startIso, endIso) {
  const a = Date.parse(startIso), b = Date.parse(endIso);
  return bars.filter(x => x.time >= a && x.time <= b);
}

const GOLD_CFG = {
  name: 'Gold Pullback Lab',
  key: 'lab_gold_1d',
  market: 'XAUUSD',
  timeframe: '1d',
  instrument_note: 'Research proxy: Yahoo GC=F continuous futures (not GLD ETF). Live bot targets XAUUSD from your broker — do not execute GC=F signals on GLD or vice versa.',
  source: 'Yahoo Finance GC=F (XAUUSD research proxy)',
  costs: 'round-trip 0.04% modelled (spread/slippage proxy); 1 unit; no financing',
  strategy: 'Trend-filtered RSI(2) pullback',
  engine: 'pullback_lab.mjs (completed-bar signals, next-open fill)',
  rsiPeriod: 2, rsiEntry: 15, rsiExit: 60, maxBars: 7,
  atrPeriod: 14, atrStopMult: 2,
  requireMomentum30: false,
  costPct: 0.02, // per side
  qty: 1,
  initialCapital: 10000,
};

const BTC_CFG = {
  name: 'BTC Pullback Lab',
  key: 'lab_btc_1d',
  market: 'BTCUSD',
  timeframe: '1d',
  instrument_note: 'BTC/USD spot daily candles (Bitstamp), 24/7 market. Separate from gold exposure limits.',
  source: 'Bitstamp BTCUSD daily',
  costs: 'round-trip 0.20% modelled (fees+slippage proxy); 0.01 BTC unit; no funding',
  strategy: 'Trend-filtered RSI(2) pullback + 30d momentum',
  engine: 'pullback_lab.mjs (completed-bar signals, next-open fill)',
  rsiPeriod: 2, rsiEntry: 10, rsiExit: 65, maxBars: 10,
  atrPeriod: 14, atrStopMult: 2,
  requireMomentum30: true,
  costPct: 0.10,
  qty: 0.01,
  initialCapital: 10000,
};

function runInstrument(csvPath, cfg, holdoutStart) {
  const all = loadCsv(csvPath);
  // Need SMA200 warm-up; use full series then filter trades by period for IS/OOS
  const full = backtest(all, cfg);
  const isTrades = full.trades_list.filter(t => t.entry < holdoutStart);
  const oosTrades = full.trades_list.filter(t => t.entry >= holdoutStart);
  const isBars = all.filter(b => b.time < Date.parse(holdoutStart));
  const oosBars = all.filter(b => b.time >= Date.parse(holdoutStart));
  const is = summarize(isTrades, isBars.length ? isBars : all, cfg);
  const oos = summarize(oosTrades, oosBars.length ? oosBars : all, cfg);
  return { cfg, full, is, oos, holdoutStart };
}

function toSet(cfg, stats, extra = {}) {
  return {
    key: cfg.key,
    market: cfg.market,
    timeframe: cfg.timeframe,
    source: cfg.source,
    costs: cfg.costs,
    instrument_note: cfg.instrument_note,
    period: `${stats.start} to ${stats.end}`,
    start: stats.start,
    end: stats.end,
    bars: stats.bars,
    strategy: cfg.strategy,
    engine: cfg.engine,
    initial_capital: cfg.initialCapital,
    trades: stats.trades,
    win_rate: stats.win_rate,
    profit_factor: stats.profit_factor,
    net: stats.net,
    net_pct: stats.net_pct,
    avg_win: stats.avg_win,
    avg_loss: stats.avg_loss,
    max_drawdown_pct: stats.max_drawdown_pct,
    sharpe: null,
    avg_bars: stats.avg_bars,
    max_consecutive_losses: stats.max_consecutive_losses,
    buy_hold_pct: stats.buy_hold_pct,
    winning_trades: stats.winning_trades,
    losing_trades: stats.losing_trades,
    largest_loss: stats.largest_loss,
    largest_win: stats.largest_win,
    equity: stats.equity,
    trades_list: stats.trades_list.map(({ entry, exit, side, entry_price, exit_price, profit, reason_exit }) =>
      ({ entry, exit, side, entry_price, exit_price, profit, reason_exit })),
    rules: {
      trend: cfg.requireMomentum30
        ? 'Close > SMA(200) and close > close[30]'
        : 'Close > SMA(200)',
      setup: `RSI(${cfg.rsiPeriod}) < ${cfg.rsiEntry}`,
      entry: 'Buy next candle open after completed signal',
      exit: `RSI(${cfg.rsiPeriod}) > ${cfg.rsiExit} OR ${cfg.maxBars} bars OR close < SMA(200)`,
      stop: `${cfg.atrStopMult}× ATR(${cfg.atrPeriod}) below entry (gap-aware)`,
      position: 'One long only; no averaging down',
    },
    ...extra,
  };
}

const HOLDOUT = '2024-01-01';
const gold = runInstrument(join(ROOT, 'data/gold_1d.csv'), GOLD_CFG, HOLDOUT);
const btc = runInstrument(join(ROOT, 'data/btc_1d.csv'), BTC_CFG, HOLDOUT);

function print(label, r) {
  console.log(`\n=== ${label} ===`);
  console.log(`Full: n=${r.full.trades} WR=${r.full.win_rate}% PF=${r.full.profit_factor} net=$${r.full.net} DD=${r.full.max_drawdown_pct}% BH=${r.full.buy_hold_pct}%`);
  console.log(`IS  (<${r.holdoutStart}): n=${r.is.trades} WR=${r.is.win_rate}% PF=${r.is.profit_factor} net=$${r.is.net}`);
  console.log(`OOS (>=${r.holdoutStart}): n=${r.oos.trades} WR=${r.oos.win_rate}% PF=${r.oos.profit_factor} net=$${r.oos.net}`);
}

print('GOLD XAUUSD proxy (GC=F)', gold);
print('BTCUSD spot', btc);

const lab = {
  generated: new Date().toISOString().slice(0, 10),
  note: 'Trend-filtered RSI pullback lab. Historical simulations with modelled costs. Not live results. Not a guarantee of future performance. Gold uses GC=F as XAUUSD research proxy — not GLD.',
  holdout_start: HOLDOUT,
  risk_defaults: {
    max_allocation_per_instrument_pct: 10,
    atr_stop_mult: 2,
    pause_after_consecutive_losses: 3,
    reject_if: ['missing_or_stale_candle', 'insufficient_funds', 'order_already_pending', 'daily_loss_limit'],
    separate_gold_and_btc_limits: true,
    combined_account_limit: true,
  },
  sets: [
    toSet(GOLD_CFG, gold.full, { is: { trades: gold.is.trades, win_rate: gold.is.win_rate, profit_factor: gold.is.profit_factor, net: gold.is.net }, oos: { trades: gold.oos.trades, win_rate: gold.oos.win_rate, profit_factor: gold.oos.profit_factor, net: gold.oos.net } }),
    toSet(BTC_CFG, btc.full, { is: { trades: btc.is.trades, win_rate: btc.is.win_rate, profit_factor: btc.is.profit_factor, net: btc.is.net }, oos: { trades: btc.oos.trades, win_rate: btc.oos.win_rate, profit_factor: btc.oos.profit_factor, net: btc.oos.net } }),
  ],
};

if (process.argv.includes('--write')) {
  const out = join(ROOT, 'portal/static/data/strategy_lab.json');
  writeFileSync(out, JSON.stringify(lab));
  console.log(`\nWrote ${out}`);

  // Merge lab sets into backtests.json (replace lab_* keys)
  const btPath = join(ROOT, 'portal/static/data/backtests.json');
  const bt = JSON.parse(readFileSync(btPath, 'utf8'));
  bt.sets = bt.sets.filter(s => !String(s.key).startsWith('lab_'));
  bt.sets.push(...lab.sets);
  bt.generated = lab.generated;
  writeFileSync(btPath, JSON.stringify(bt));
  console.log(`Merged lab sets into ${btPath}`);
}
