import secrets

from django.conf import settings
from django.db import models
from django.utils import timezone

from . import crypto
from .markets import MARKETS, TIMEFRAMES

BROKERS = [("none", "No broker (paper only)"), ("binance", "Binance Futures (USDT-M)"), ("exness", "Exness (MetaTrader 5)")]
MODES = [("paper", "Paper trading (simulated)"), ("live", "Live trading (real money)")]


class BotSettings(models.Model):
    """One trading bot per customer: what it may trade, how much it may risk, and the kill switch."""
    user = models.OneToOneField(settings.AUTH_USER_MODEL, on_delete=models.CASCADE, related_name="bot")
    enabled = models.BooleanField(default=False, help_text="Master switch set by the customer.")
    kill_switch = models.BooleanField(default=False, help_text="Emergency stop: blocks every new order until cleared.")
    mode = models.CharField(max_length=8, choices=MODES, default="paper")
    broker = models.CharField(max_length=12, choices=BROKERS, default="none")
    strategy = models.CharField(max_length=40, default="VWAP Reversal")
    markets = models.CharField(max_length=60, default="BTCUSD", help_text="Comma-separated canonical symbols the bot may trade.")
    timeframes = models.CharField(max_length=40, default="60", help_text="Comma-separated TradingView timeframes (5,15,30,60,240).")
    # risk
    risk_pct = models.FloatField(default=1.0)
    max_daily_loss_pct = models.FloatField(default=5.0)
    max_open_trades = models.PositiveSmallIntegerField(default=1)
    max_position_size = models.FloatField(default=0, help_text="Units (BTC / lots); 0 = no cap.")
    max_exposure_pct = models.FloatField(default=20.0, help_text="Max notional as % of equity across open trades.")
    max_consecutive_losses = models.PositiveSmallIntegerField(default=3)
    daily_trade_limit = models.PositiveSmallIntegerField(default=5)
    leverage = models.PositiveSmallIntegerField(default=3)
    paper_capital = models.FloatField(default=10000)
    # exits
    sl_mode = models.CharField(max_length=10, default="signal", choices=[("signal", "Use the signal's stop"), ("pct", "Fixed % from entry")])
    sl_pct = models.FloatField(default=0.5)
    tp_mode = models.CharField(max_length=10, default="signal", choices=[("signal", "Use the signal's target"), ("rr", "Risk/reward multiple")])
    rr = models.FloatField(default=1.5)
    breakeven_at_r = models.FloatField(default=1.0, help_text="Move stop to entry after this many R of profit; 0 = off.")
    trailing_enabled = models.BooleanField(default=False)
    trailing_pct = models.FloatField(default=0.4, help_text="Trail distance as % of price.")
    respect_market_hours = models.BooleanField(default=True)
    # own TradingView webhook (in addition to platform signals)
    webhook_token = models.CharField(max_length=48, unique=True, blank=True)
    accept_platform_signals = models.BooleanField(default=True, help_text="Trade the signals published by the platform.")
    accept_own_signals = models.BooleanField(default=True, help_text="Trade signals sent to the personal webhook URL.")
    telegram_chat_id = models.CharField(max_length=32, blank=True)
    updated = models.DateTimeField(auto_now=True)
    created = models.DateTimeField(auto_now_add=True)

    def save(self, *args, **kwargs):
        if not self.webhook_token:
            self.webhook_token = secrets.token_urlsafe(24)
        super().save(*args, **kwargs)

    def __str__(self):
        return f"bot of {self.user.username} ({'on' if self.active else 'off'})"

    @property
    def active(self) -> bool:
        return self.enabled and not self.kill_switch

    @property
    def market_list(self):
        return [m for m in self.markets.split(",") if m in MARKETS]

    @property
    def timeframe_list(self):
        return [t for t in self.timeframes.split(",") if t in dict(TIMEFRAMES)]

    def connection(self):
        return self.user.broker_connections.filter(broker=self.broker).first() if self.broker != "none" else None

    def to_engine(self) -> dict:
        """Everything the trading engine needs, with decrypted credentials. Never sent to a browser."""
        conn = self.connection()
        return {
            "user_id": self.user_id, "username": self.user.username, "active": self.active, "mode": self.mode, "broker": self.broker,
            "markets": self.market_list, "timeframes": self.timeframe_list, "risk_pct": self.risk_pct, "max_daily_loss_pct": self.max_daily_loss_pct,
            "max_open_trades": self.max_open_trades, "max_position_size": self.max_position_size, "max_exposure_pct": self.max_exposure_pct,
            "max_consecutive_losses": self.max_consecutive_losses, "daily_trade_limit": self.daily_trade_limit, "leverage": self.leverage,
            "paper_capital": self.paper_capital, "sl_mode": self.sl_mode, "sl_pct": self.sl_pct, "tp_mode": self.tp_mode, "rr": self.rr,
            "breakeven_at_r": self.breakeven_at_r, "trailing_enabled": self.trailing_enabled, "trailing_pct": self.trailing_pct,
            "respect_market_hours": self.respect_market_hours, "accept_platform_signals": self.accept_platform_signals,
            "accept_own_signals": self.accept_own_signals, "webhook_token": self.webhook_token, "telegram_chat_id": self.telegram_chat_id,
            "credentials": conn.decrypted() if conn else {},
        }


class BrokerConnection(models.Model):
    user = models.ForeignKey(settings.AUTH_USER_MODEL, on_delete=models.CASCADE, related_name="broker_connections")
    broker = models.CharField(max_length=12, choices=BROKERS[1:])
    api_key_enc = models.TextField(blank=True)
    api_secret_enc = models.TextField(blank=True)
    extra_enc = models.TextField(blank=True, help_text="Encrypted JSON: testnet flag, MT5 login/server/password, bridge URL.")
    status = models.CharField(max_length=12, default="unverified")   # unverified / ok / error
    last_error = models.CharField(max_length=200, blank=True)
    balance = models.FloatField(null=True, blank=True)
    equity = models.FloatField(null=True, blank=True)
    last_checked = models.DateTimeField(null=True, blank=True)
    # live health reported by the MT5 bridge (see bots/health.py): only a fresh, authenticated heartbeat proves a connection
    last_heartbeat = models.DateTimeField(null=True, blank=True)
    terminal_connected = models.BooleanField(default=False, help_text="The MT5 terminal is logged in to the broker.")
    identity_verified = models.BooleanField(default=False, help_text="The account the terminal reports matches the login saved here.")
    trade_allowed = models.BooleanField(default=False, help_text="The account and terminal permit automated trading.")
    account_mode = models.CharField(max_length=8, blank=True, help_text="demo / real / contest, as reported by the terminal.")
    reported_login = models.CharField(max_length=24, blank=True)
    reported_server = models.CharField(max_length=60, blank=True)
    error_code = models.CharField(max_length=24, blank=True, help_text="auth_failed / terminal_disconnected / account_mismatch / other")
    created = models.DateTimeField(auto_now_add=True)

    class Meta:
        unique_together = ("user", "broker")

    def set_credentials(self, api_key: str, api_secret: str, extra: dict | None = None):
        import json
        if api_key:
            self.api_key_enc = crypto.encrypt(api_key)
        if api_secret:
            self.api_secret_enc = crypto.encrypt(api_secret)
        if extra is not None:
            self.extra_enc = crypto.encrypt(json.dumps(extra))
        self.status = "unverified"

    def decrypted(self) -> dict:
        import json
        try:
            extra = json.loads(crypto.decrypt(self.extra_enc) or "{}")
        except ValueError:
            extra = {}
        return {"broker": self.broker, "api_key": crypto.decrypt(self.api_key_enc), "api_secret": crypto.decrypt(self.api_secret_enc), **extra}

    @property
    def api_key_masked(self):
        return crypto.mask(crypto.decrypt(self.api_key_enc))


class Execution(models.Model):
    """One decision of the engine for one customer: rejected, opened, closed or error."""
    STATUS = [("rejected", "Rejected by risk rules"), ("open", "Open"), ("closed", "Closed"), ("error", "Broker error")]
    user = models.ForeignKey(settings.AUTH_USER_MODEL, on_delete=models.CASCADE, related_name="executions")
    signal_ref = models.CharField(max_length=80, blank=True, db_index=True)
    source = models.CharField(max_length=12, default="platform")   # platform / own
    mode = models.CharField(max_length=8, default="paper")
    broker = models.CharField(max_length=12, default="none")
    symbol = models.CharField(max_length=16)
    timeframe = models.CharField(max_length=8, blank=True)
    side = models.CharField(max_length=5)
    qty = models.FloatField(default=0)
    entry = models.FloatField(null=True, blank=True)
    sl = models.FloatField(null=True, blank=True)
    tp = models.FloatField(null=True, blank=True)
    initial_sl = models.FloatField(null=True, blank=True)
    exit_price = models.FloatField(null=True, blank=True)
    pnl = models.FloatField(null=True, blank=True)
    r_multiple = models.FloatField(null=True, blank=True)
    status = models.CharField(max_length=10, choices=STATUS)
    reason = models.CharField(max_length=200, blank=True)
    order_id = models.CharField(max_length=80, blank=True)
    opened_at = models.DateTimeField(default=timezone.now)
    closed_at = models.DateTimeField(null=True, blank=True)
    updated = models.DateTimeField(auto_now=True)
    raw = models.JSONField(default=dict, blank=True)

    class Meta:
        ordering = ["-opened_at"]

    def __str__(self):
        return f"{self.user.username} {self.side} {self.symbol} {self.status}"


class BotEvent(models.Model):
    """Audit trail for a customer's bot: settings changes, kill switch, broker checks, engine notices."""
    user = models.ForeignKey(settings.AUTH_USER_MODEL, on_delete=models.CASCADE, related_name="bot_events")
    kind = models.CharField(max_length=24)
    text = models.CharField(max_length=300)
    created = models.DateTimeField(auto_now_add=True)

    class Meta:
        ordering = ["-created"]
