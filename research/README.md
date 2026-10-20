# Research toolkit (backtests and walk-forward tests)

Runs the Pine strategies in this repository against the CSV files in `../data` using
[piner](https://github.com/heyphat/piner), an open-source Pine Script v6 engine. This is the
same harness that produced every number quoted in the strategy headers.

```bash
cd research
npm install
node backtest.mjs ../tradingview_vwap_reversal_axealgo_strategy.pine ../data/gold_1h.csv 60 0.1 --commission 0 --slippage 3
node walkforward.mjs ../tradingview_vwap_reversal_axealgo_strategy.pine ../data/gold_1h.csv 60 0.1 grids/vwap_reversal.json --commission 0 --slippage 3
node backtest.mjs ../tradingview_psl_toolkit_axealgo_strategy.pine ../data/btc_1d.csv D 0.01 --set "TP Distance (ATR x)=6" --set "Enable Trend EMA Filter=true"
node fetch_data.mjs        # refresh ../data from Binance / Bitstamp / Yahoo (no keys needed)
```

Arguments: strategy file, CSV, chart timeframe (`5`, `15`, `60`, `240`, `D`), tick size
(`0.1` gold, `0.01` BTC), then options. Costs: gold CFDs have no commission but a spread
(use `--commission 0 --slippage 3`); Binance futures roughly `--commission 0.05 --slippage 2`.
`--set "Input Title=value"` overrides any strategy input by its exact title.

## What "training the bot" means here

There is no neural network to train: a trading strategy is a set of rules with parameters.
"Training" = choosing parameters on one part of history (in-sample) and checking that they still
work on a later part the choice never saw (out-of-sample). `walkforward.mjs` does exactly that and
prints both. Rules of thumb learned from these datasets:

- Settings that win in-sample and lose out-of-sample were curve-fitted; ignore them.
- A high win rate is easy to manufacture (tiny target, wide stop) and lost money out-of-sample
  on 26 years of gold and 15 years of BTC. Judge by profit factor, drawdown and trade count.
- Fewer than ~100 trades is a small sample; expect live results to be worse than the backtest.
- Bitcoin has ~15 years of history (since 2010/2011). Gold daily has 26 years. Intraday history
  is limited by the free sources (1h ≈ 2 years, 5m/15m ≈ 60 days).

## Engine limitations

piner is a clean-room engine, not TradingView. It matched TradingView's Strategy Tester closely
in our checks, but partial exits (`strategy.exit(..., qty_percent=50)`) close the whole position in
piner, so the VWAP strategy's optional TP1 partial cannot be evaluated here; leave TP1 at 0 for
research and verify partials in TradingView's List of Trades.
