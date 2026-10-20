// Backtest one strategy on one CSV.
//   node backtest.mjs <strategy.pine> <data.csv> <timeframe> <mintick> [--commission 0.05] [--slippage 2] [--set "Input Title=value"]... [--trades]
// Examples:
//   node backtest.mjs ../tradingview_vwap_reversal_axealgo_strategy.pine ../data/gold_1h.csv 60 0.1 --commission 0 --slippage 3
//   node backtest.mjs ../tradingview_psl_toolkit_axealgo_strategy.pine ../data/btc_1d.csv D 0.01 --set "TP Distance (ATR x)=6" --set "Enable Trend EMA Filter=true"
import { compileStrategy, loadCsv, runStrategy, tradeStats, fmt, parseSets, flag } from './lib.mjs';

const [strategyPath, dataPath, tf, mintickArg] = process.argv.slice(2);
if (!strategyPath || !dataPath || !tf || !mintickArg) {
  console.log('usage: node backtest.mjs <strategy.pine> <data.csv> <timeframe e.g. 60|240|D> <mintick> [--commission %] [--slippage ticks] [--set "Title=value"]... [--trades]');
  process.exit(1);
}
const argv = process.argv.slice(6);
const costs = { commissionValue: flag(argv, '--commission', 0.05), slippage: flag(argv, '--slippage', 2) };
const inputs = parseSets(argv);
const compiled = compileStrategy(strategyPath);
const bars = loadCsv(dataPath);
const { report, metrics } = await runStrategy(compiled, bars, { tf, mintick: +mintickArg, inputs, costs });
const s = tradeStats(report.closedTrades);

console.log(`\n${compiled.metadata.title}  on  ${dataPath}  (${bars.length} bars, tf ${tf})`);
console.log(`inputs: ${JSON.stringify(inputs)} | commission ${costs.commissionValue}% | slippage ${costs.slippage} ticks`);
console.log(`trades ${s.trades} | win rate ${fmt(s.winRate, 1)}% | profit factor ${fmt(s.profitFactor)} | net $${fmt(s.net, 0)} (${fmt(report.netProfit / report.initialCapital * 100, 1)}%)`);
console.log(`avg win $${fmt(s.avgWin, 0)} | avg loss $${fmt(s.avgLoss, 0)} | max drawdown ${fmt(report.maxDrawdownPercent, 1)}% | sharpe ${fmt(metrics.sharpe)} | avg bars in trade ${fmt(metrics.avgBarsInTrade, 1)}`);
console.log(`max consecutive losses ${metrics.maxConsecutiveLosses} | buy & hold over same period ${fmt(metrics.buyHoldReturnPercent, 1)}%`);
if (argv.includes('--trades')) {
  console.log('\nentry_time,exit_time,side,qty,entry,exit,profit');
  for (const t of report.closedTrades) console.log(`${new Date(t.entryTime).toISOString()},${new Date(t.exitTime).toISOString()},${t.dir > 0 ? 'long' : 'short'},${t.qty},${t.entryPrice},${t.exitPrice},${t.profit.toFixed(2)}`);
}
