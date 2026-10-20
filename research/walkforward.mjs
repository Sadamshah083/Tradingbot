// Walk-forward parameter test: try every combination in a grid, rank by IN-SAMPLE result (first part of the data),
// then show how the same settings did OUT-OF-SAMPLE (the rest). If the winners fall apart out of sample, the
// "improvement" was curve-fitting, not skill. This is the honest version of "training a bot".
//   node walkforward.mjs <strategy.pine> <data.csv> <timeframe> <mintick> <grid.json> [--split 0.6] [--commission 0.05] [--slippage 2] [--min-trades 30] [--top 8]
// grid.json: { "Input Title": [v1, v2, ...], ... }   (see grids/*.json)
import { readFileSync } from 'node:fs';
import { compileStrategy, loadCsv, runStrategy, tradeStats, fmt, flag } from './lib.mjs';

const [strategyPath, dataPath, tf, mintickArg, gridPath] = process.argv.slice(2);
if (!gridPath) {
  console.log('usage: node walkforward.mjs <strategy.pine> <data.csv> <timeframe> <mintick> <grid.json> [--split 0.6] [--commission %] [--slippage ticks] [--min-trades 30] [--top 8]');
  process.exit(1);
}
const argv = process.argv.slice(7);
const split = flag(argv, '--split', 0.6), minTrades = flag(argv, '--min-trades', 30), top = flag(argv, '--top', 8);
const costs = { commissionValue: flag(argv, '--commission', 0.05), slippage: flag(argv, '--slippage', 2) };
const grid = JSON.parse(readFileSync(gridPath, 'utf8'));
const compiled = compileStrategy(strategyPath);
const bars = loadCsv(dataPath);
const splitTime = bars[Math.floor(bars.length * split)].time;

const keys = Object.keys(grid);
const combos = keys.reduce((acc, k) => acc.flatMap(a => grid[k].map(v => ({ ...a, [k]: v }))), [{}]);
console.log(`${compiled.metadata.title} on ${dataPath}: ${combos.length} combinations, split at ${new Date(splitTime).toISOString().slice(0, 10)} (${Math.round(split * 100)}% in-sample)`);

const rows = [];
const t0 = Date.now();
for (const inputs of combos) {
  const { report } = await runStrategy(compiled, bars, { tf, mintick: +mintickArg, inputs, costs });
  const is = tradeStats(report.closedTrades.filter(t => t.entryTime < splitTime));
  const oos = tradeStats(report.closedTrades.filter(t => t.entryTime >= splitTime));
  rows.push({ inputs, is, oos });
}
const eligible = rows.filter(r => r.is.trades >= minTrades);
const ranked = [...eligible].sort((a, b) => b.is.profitFactor - a.is.profitFactor);
const profitableIs = eligible.filter(r => r.is.profitFactor >= 1.1).length;
const profitableOos = rows.filter(r => r.oos.trades >= Math.max(10, minTrades / 3) && r.oos.profitFactor >= 1.1).length;
console.log(`done in ${((Date.now() - t0) / 1000).toFixed(0)}s | profitable in-sample (PF>=1.1, >=${minTrades} trades): ${profitableIs}/${eligible.length} | profitable out-of-sample: ${profitableOos}/${rows.length}\n`);
const line = (s) => `${s.trades} trades, win ${fmt(s.winRate, 1)}%, PF ${fmt(s.profitFactor)}, net $${fmt(s.net, 0)}, maxDD $${fmt(s.maxDrawdown$, 0)}`;
ranked.slice(0, top).forEach((r, i) => {
  console.log(`${i + 1}. ${JSON.stringify(r.inputs)}\n     in-sample:      ${line(r.is)}\n     OUT-OF-SAMPLE:  ${line(r.oos)}`);
});
const survivors = ranked.slice(0, top).filter(r => r.oos.profitFactor >= 1.1).length;
console.log(`\nOf the top ${Math.min(top, ranked.length)} in-sample settings, ${survivors} stayed profitable out of sample. Trust only settings that survive here AND make sense.`);
