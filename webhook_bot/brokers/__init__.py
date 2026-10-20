"""Broker adapters. `make_broker()` picks one from the BROKER env variable.

Every adapter implements:
    name: str
    async open_position(symbol, side, qty, sl, tp) -> dict
    async close_all(symbol) -> dict
"""
from __future__ import annotations

import os

from .paper import PaperBroker


def make_broker(live: bool):
    kind = os.getenv("BROKER", "paper").lower()
    if not live or kind == "paper":
        return PaperBroker()
    if kind == "oanda":
        from .oanda import OandaBroker
        return OandaBroker()
    if kind == "binance_futures":
        from .binance_futures import BinanceFuturesBroker
        return BinanceFuturesBroker()
    raise SystemExit(f"unknown BROKER '{kind}' (use paper, oanda or binance_futures)")
