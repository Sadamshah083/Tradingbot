"""OANDA v20 REST adapter (gold / forex CFDs).

Env: OANDA_TOKEN, OANDA_ACCOUNT_ID, OANDA_ENV = practice | live
Symbols must be OANDA instruments, e.g. XAU_USD (map TradingView's XAUUSD via SYMBOL_MAP).
Units are whole numbers on OANDA; quantities are rounded DOWN.
"""
from __future__ import annotations

import math
import os

import httpx


class OandaBroker:
    name = "oanda"

    def __init__(self) -> None:
        self.token = os.environ["OANDA_TOKEN"]
        self.account = os.environ["OANDA_ACCOUNT_ID"]
        env = os.getenv("OANDA_ENV", "practice").lower()
        self.base = "https://api-fxtrade.oanda.com" if env == "live" else "https://api-fxpractice.oanda.com"
        self._precision: dict[str, int] = {}
        self._client = httpx.AsyncClient(
            base_url=self.base,
            headers={"Authorization": f"Bearer {self.token}", "Content-Type": "application/json"},
            timeout=10.0,
        )

    async def _precision_for(self, instrument: str) -> int:
        if instrument not in self._precision:
            r = await self._client.get(f"/v3/accounts/{self.account}/instruments", params={"instruments": instrument})
            r.raise_for_status()
            for ins in r.json().get("instruments", []):
                self._precision[ins["name"]] = int(ins["displayPrecision"])
        return self._precision.get(instrument, 3)

    async def open_position(self, symbol: str, side: str, qty: float, sl: float, tp: float) -> dict:
        units = int(math.floor(qty))
        if units < 1:
            return {"skipped": "quantity below 1 unit", "qty": qty}
        if side == "sell":
            units = -units
        digits = await self._precision_for(symbol)
        body = {
            "order": {
                "type": "MARKET",
                "instrument": symbol,
                "units": str(units),
                "timeInForce": "FOK",
                "positionFill": "DEFAULT",
                "stopLossOnFill": {"price": f"{sl:.{digits}f}", "timeInForce": "GTC"},
                "takeProfitOnFill": {"price": f"{tp:.{digits}f}", "timeInForce": "GTC"},
            }
        }
        r = await self._client.post(f"/v3/accounts/{self.account}/orders", json=body)
        data = r.json()
        if r.status_code >= 400:
            return {"error": data}
        fill = data.get("orderFillTransaction", {})
        return {"order_id": data.get("orderCreateTransaction", {}).get("id"), "filled_units": fill.get("units"), "price": fill.get("price")}

    async def close_all(self, symbol: str) -> dict:
        r = await self._client.get(f"/v3/accounts/{self.account}/positions/{symbol}")
        if r.status_code == 404:
            return {"closed": "nothing open"}
        r.raise_for_status()
        pos = r.json().get("position", {})
        body = {}
        if float(pos.get("long", {}).get("units", 0)) > 0:
            body["longUnits"] = "ALL"
        if float(pos.get("short", {}).get("units", 0)) < 0:
            body["shortUnits"] = "ALL"
        if not body:
            return {"closed": "nothing open"}
        r = await self._client.put(f"/v3/accounts/{self.account}/positions/{symbol}/close", json=body)
        return {"status": r.status_code, "response": r.json()}
