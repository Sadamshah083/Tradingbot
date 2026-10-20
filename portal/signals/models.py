from django.conf import settings
from django.db import models


class Signal(models.Model):
    """A TradingView event forwarded by the webhook bot (signal / entry / exit)."""
    event = models.CharField(max_length=16)
    side = models.CharField(max_length=8, blank=True)
    symbol = models.CharField(max_length=32)
    timeframe = models.CharField(max_length=8, blank=True)
    strategy = models.CharField(max_length=64, blank=True)
    price = models.FloatField(null=True, blank=True)
    sl = models.FloatField(null=True, blank=True)
    tp1 = models.FloatField(null=True, blank=True)
    tp2 = models.FloatField(null=True, blank=True)
    qty = models.FloatField(null=True, blank=True)
    reason = models.CharField(max_length=32, blank=True)
    external_id = models.CharField(max_length=64, blank=True, db_index=True)
    raw = models.JSONField(default=dict)
    source = models.CharField(max_length=16, default="bot", help_text="bot = forwarded from TradingView, admin = typed in by the owner")
    closed = models.BooleanField(default=False, help_text="Marked closed by the owner (or superseded by an exit event).")
    result = models.CharField(max_length=16, blank=True, help_text="Optional outcome noted by the owner: tp / sl / be / manual")
    created = models.DateTimeField(auto_now_add=True)

    class Meta:
        ordering = ["-created"]

    def __str__(self):
        return f"{self.event} {self.side} {self.symbol} {self.timeframe} @ {self.price}"

    @property
    def is_signal(self):
        return self.event == "signal"

    def text(self) -> str:
        if self.is_signal:
            return f"{self.side.upper()} {self.symbol} {self.timeframe} | entry {self.price} | SL {self.sl} | TP {self.tp2}" + (f" | TP1 {self.tp1}" if self.tp1 else "")
        return f"EXIT {self.symbol} ({self.reason}) - close the trade if still open."


class SignalDelivery(models.Model):
    """One customer receiving one signal; a credit is charged for 'signal' events."""
    signal = models.ForeignKey(Signal, on_delete=models.CASCADE, related_name="deliveries")
    user = models.ForeignKey(settings.AUTH_USER_MODEL, on_delete=models.CASCADE, related_name="signal_deliveries")
    charged = models.BooleanField(default=False)
    credits_after = models.IntegerField(default=0)
    telegram_sent = models.BooleanField(default=False)
    created = models.DateTimeField(auto_now_add=True)

    class Meta:
        ordering = ["-created"]
        unique_together = ("signal", "user")
