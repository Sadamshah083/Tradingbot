"""Paper broker: records every order to logs/paper_trades.jsonl and touches no exchange."""
from __future__ import annotations

import json
import os
import time
from pathlib import Path


class PaperBroker:
    name = "paper"

    def __init__(self) -> None:
        self.path = Path(os.getenv("LOG_DIR", "logs")) / "paper_trades.jsonl"
        self.path.parent.mkdir(parents=True, exist_ok=True)

    def _write(self, record: dict) -> dict:
        record = {"time": time.time(), **record}
        with self.path.open("a", encoding="utf-8") as fh:
            fh.write(json.dumps(record) + "\n")
        return record

    async def open_position(self, symbol: str, side: str, qty: float, sl: float, tp: float) -> dict:
        return self._write({"action": "open", "symbol": symbol, "side": side, "qty": qty, "sl": sl, "tp": tp})

    async def close_all(self, symbol: str) -> dict:
        return self._write({"action": "close_all", "symbol": symbol})
