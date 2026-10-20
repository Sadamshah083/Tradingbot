"""Binance USDT-M futures adapter via ccxt (BTC and other perpetuals).

Env: BINANCE_API_KEY, BINANCE_API_SECRET, BINANCE_TESTNET = true | false, BINANCE_LEVERAGE (optional)
Symbols must be ccxt unified futures symbols, e.g. BTC/USDT:USDT (map TradingView's BTCUSDT via SYMBOL_MAP).
Entry = market order; stop-loss = STOP_MARKET reduce-only; take-profit = TAKE_PROFIT_MARKET reduce-only.
"""
from __future__ import annotations

import os

import ccxt.async_support as ccxt


class BinanceFuturesBroker:
    name = "binance_futures"

    def __init__(self) -> None:
        self.ex = ccxt.binanceusdm({
            "apiKey": os.environ["BINANCE_API_KEY"],
            "secret": os.environ["BINANCE_API_SECRET"],
            "enableRateLimit": True,
            "options": {"defaultType": "future"},
        })
        if os.getenv("BINANCE_TESTNET", "true").lower() == "true":
            self.ex.set_sandbox_mode(True)
        self.leverage = int(os.getenv("BINANCE_LEVERAGE", "0"))
        self._loaded = False

    async def _ready(self, symbol: str) -> None:
        if not self._loaded:
            await self.ex.load_markets()
            self._loaded = True
        if self.leverage > 0:
            try:
                await self.ex.set_leverage(self.leverage, symbol)
            except Exception:
                pass  # already set or not supported on this account type

    async def open_position(self, symbol: str, side: str, qty: float, sl: float, tp: float) -> dict:
        await self._ready(symbol)
        amount = float(self.ex.amount_to_precision(symbol, qty))
        if amount <= 0:
            return {"skipped": "quantity rounds to zero", "qty": qty}
        opposite = "sell" if side == "buy" else "buy"
        entry = await self.ex.create_order(symbol, "market", side, amount)
        sl_order = await self.ex.create_order(symbol, "STOP_MARKET", opposite, amount, None,
                                              {"stopPrice": float(self.ex.price_to_precision(symbol, sl)), "reduceOnly": True})
        tp_order = await self.ex.create_order(symbol, "TAKE_PROFIT_MARKET", opposite, amount, None,
                                              {"stopPrice": float(self.ex.price_to_precision(symbol, tp)), "reduceOnly": True})
        return {"entry": entry.get("id"), "sl": sl_order.get("id"), "tp": tp_order.get("id"), "amount": amount}

    async def close_all(self, symbol: str) -> dict:
        await self._ready(symbol)
        try:
            await self.ex.cancel_all_orders(symbol)
        except Exception as exc:
            cancel = f"cancel failed: {exc}"
        else:
            cancel = "open orders cancelled"
        positions = await self.ex.fetch_positions([symbol])
        closed = []
        for p in positions:
            contracts = float(p.get("contracts") or 0)
            if contracts <= 0:
                continue
            side = "sell" if p.get("side") == "long" else "buy"
            order = await self.ex.create_order(symbol, "market", side, contracts, None, {"reduceOnly": True})
            closed.append({"side": side, "contracts": contracts, "id": order.get("id")})
        return {"cancel": cancel, "closed": closed or "nothing open"}
