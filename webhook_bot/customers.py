"""Paying signal customers: stored in logs/customers.json, each with Telegram chat id and signal credits.

deliver(text, charge=True) sends the text to every active customer; when charge is True one credit is
deducted per successfully delivered signal (customers with 0 credits receive nothing).
"""
from __future__ import annotations

import json
import time
import uuid

import core

FILE = core.LOG_DIR / "customers.json"


def load() -> list[dict]:
    if not FILE.exists():
        return []
    try:
        return json.loads(FILE.read_text(encoding="utf-8"))
    except json.JSONDecodeError:
        return []


def save(items: list[dict]) -> None:
    FILE.write_text(json.dumps(items, indent=2), encoding="utf-8")


def add(name: str, telegram_chat_id: str, email: str, credits: int, note: str = "") -> dict:
    items = load()
    c = {"id": uuid.uuid4().hex[:8], "name": name.strip()[:60], "telegram_chat_id": telegram_chat_id.strip(), "email": email.strip()[:80],
         "credits": max(0, int(credits)), "purchased": max(0, int(credits)), "used": 0, "active": True, "note": note.strip()[:120],
         "created": time.time(), "last_delivery": None}
    items.append(c)
    save(items)
    core.log.info("customer added: %s (%s) credits=%s", c["name"], c["id"], c["credits"])
    return c


def update(cid: str, **changes) -> dict | None:
    items = load()
    for c in items:
        if c["id"] == cid:
            if "add_credits" in changes:
                n = max(0, int(changes.pop("add_credits") or 0))
                c["credits"] += n
                c["purchased"] += n
            for k, v in changes.items():
                if k in ("name", "telegram_chat_id", "email", "note", "active"):
                    c[k] = v
            save(items)
            core.log.info("customer updated: %s -> %s", cid, changes)
            return c
    return None


def delete(cid: str) -> bool:
    items = load()
    kept = [c for c in items if c["id"] != cid]
    if len(kept) == len(items):
        return False
    save(kept)
    core.log.info("customer deleted: %s", cid)
    return True


def summary() -> dict:
    items = load()
    return {"total": len(items), "active": sum(1 for c in items if c["active"]), "credits_outstanding": sum(c["credits"] for c in items if c["active"]),
            "signals_delivered": sum(c["used"] for c in items)}


async def deliver(text: str, charge: bool) -> int:
    """Send `text` to every active customer (with credits when charge=True). Returns the number delivered."""
    items = load()
    delivered = 0
    for c in items:
        if not c.get("active") or not c.get("telegram_chat_id"):
            continue
        if charge and c.get("credits", 0) <= 0:
            continue
        ok = await core.telegram_send(c["telegram_chat_id"], text + (f"\n\nCredits left after this signal: {c['credits'] - 1}" if charge else ""))
        if ok:
            delivered += 1
            c["last_delivery"] = time.time()
            if charge:
                c["credits"] -= 1
                c["used"] += 1
    if delivered:
        save(items)
        core.append_journal("deliveries.jsonl", {"charge": charge, "delivered": delivered, "text": text[:200]})
    return delivered
