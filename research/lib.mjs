// Shared helpers: CSV loading, resampling, running a Pine strategy through the piner engine, statistics.
import { readFileSync } from 'node:fs';
import { compile, Engine, ArrayFeed } from '@heyphat/piner';

export function loadCsv(path) {
  const lines = readFileSync(path, 'utf8').trim().split(/\r?\n/);
  const header = lines[0].split(',');
  const idx = (name) => header.indexOf(name);
  const iT = idx('timestamp_ms'), iO = idx('open'), iH = idx('high'), iL = idx('low'), iC = idx('close'), iV = idx('volume');
  const bars = [];
  for (let i = 1; i < lines.length; i++) {
    const c = lines[i].split(',');
    bars.push({ time: +c[iT], open: +c[iO], high: +c[iH], low: +c[iL], close: +c[iC], volume: +c[iV] });
  }
  return bars;
}

export function resample(bars, hours) {
  const ms = hours * 3600 * 1000, out = [];
  let cur = null, key = null;
  for (const b of bars) {
    const k = Math.floor(b.time / ms);
    if (k !== key) { if (cur) out.push(cur); key = k; cur = { time: k * ms, open: b.open, high: b.high, low: b.low, close: b.close, volume: b.volume }; }
    else { cur.high = Math.max(cur.high, b.high); cur.low = Math.min(cur.low, b.low); cur.close = b.close; cur.volume += b.volume; }
  }
  if (cur) out.push(cur);
  return out;
}

export function compileStrategy(path) {
  const compiled = compile(readFileSync(path, 'utf8'));
  if (compiled.diagnostics.length) console.warn('compiler diagnostics:', compiled.diagnostics);
  return compiled;
}

/** Run one backtest. costs = { commissionValue (percent), slippage (ticks) }. inputs keyed by input title. */
export async function runStrategy(compiled, bars, { tf, mintick, inputs = {}, costs = {} }) {
  const strategy = {};
  if (costs.commissionValue !== undefined) { strategy.commissionType = 'percent'; strategy.commissionValue = costs.commissionValue; }
  if (costs.slippage !== undefined) strategy.slippage = costs.slippage;
  const engine = new Engine(compiled, new ArrayFeed(bars), { inputs, strategy });
  await engine.run({ symbol: 'X', timeframe: tf, mintick });
  return { report: engine.strategy, metrics: engine.strategyMetrics(), engine };
}

export function tradeStats(trades) {
  const n = trades.length;
  const wins = trades.filter(t => t.profit > 0);
  const gp = wins.reduce((a, t) => a + t.profit, 0);
  const gl = trades.filter(t => t.profit < 0).reduce((a, t) => a + t.profit, 0);
  let peak = 0, equity = 0, maxDd = 0;
  for (const t of trades) { equity += t.profit; peak = Math.max(peak, equity); maxDd = Math.max(maxDd, peak - equity); }
  return {
    trades: n,
    winRate: n ? wins.length / n * 100 : 0,
    profitFactor: gl !== 0 ? gp / Math.abs(gl) : (gp > 0 ? Infinity : 0),
    net: gp + gl,
    avgWin: wins.length ? gp / wins.length : 0,
    avgLoss: n - wins.length ? gl / (n - wins.length) : 0,
    maxDrawdown$: maxDd,
  };
}

export const fmt = (n, d = 2) => Number.isFinite(n) ? n.toFixed(d) : (n === Infinity ? 'inf' : 'n/a');

/** Parse "--set Title=value" pairs into an inputs object, converting numbers/booleans. */
export function parseSets(argv) {
  const inputs = {};
  for (let i = 0; i < argv.length; i++) {
    if (argv[i] === '--set' && argv[i + 1]) {
      const [title, ...rest] = argv[i + 1].split('=');
      let v = rest.join('=').trim();
      if (v === 'true') v = true; else if (v === 'false') v = false; else if (v !== '' && !Number.isNaN(Number(v))) v = Number(v);
      inputs[title.trim()] = v;
      i++;
    }
  }
  return inputs;
}

export function flag(argv, name, def) {
  const i = argv.indexOf(name);
  if (i === -1 || !argv[i + 1]) return def;
  const v = argv[i + 1];
  return Number.isNaN(Number(v)) ? v : Number(v);
}
