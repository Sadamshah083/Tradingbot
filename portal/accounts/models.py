from django.conf import settings
from django.db import models


class Profile(models.Model):
    """Customer account details: signal credits, Telegram, status."""
    user = models.OneToOneField(settings.AUTH_USER_MODEL, on_delete=models.CASCADE, related_name="profile")
    credits = models.PositiveIntegerField(default=0, help_text="Signals this customer can still receive.")
    purchased = models.PositiveIntegerField(default=0)
    used = models.PositiveIntegerField(default=0)
    telegram_chat_id = models.CharField(max_length=32, blank=True, help_text="Optional: also deliver signals to this Telegram chat.")
    active = models.BooleanField(default=True, help_text="Paused customers receive nothing, even with credits.")
    note = models.CharField(max_length=200, blank=True, help_text="Payment reference, plan, anything useful.")
    bot_access = models.BooleanField(default=False, help_text="Has bought the bot package and may download it.")
    bot_access_granted = models.DateTimeField(null=True, blank=True)
    bot_access_until = models.DateTimeField(null=True, blank=True, help_text="Bot access expires here; each $ package payment adds BOT_ACCESS_DAYS.")
    tradingview_username = models.CharField(max_length=60, blank=True, help_text="For invite-only access to the strategy on TradingView.")
    tv_access_granted = models.BooleanField(default=False, help_text="Admin has added this TradingView username to the invite-only strategy.")
    role = models.CharField(max_length=10, default="customer", choices=[("customer", "Customer"), ("agent", "Agent"), ("admin", "Admin")],
                            help_text="Staff role. The single superadmin is the Django superuser, not a role.")
    last_seen = models.DateTimeField(null=True, blank=True, help_text="Last time this staff member had the chat inbox open.")
    created = models.DateTimeField(auto_now_add=True)

    def __str__(self):
        return f"{self.user.username} ({self.credits} credits)"

    @property
    def bot_active_access(self) -> bool:
        """Paid and not expired."""
        from django.utils import timezone
        return bool(self.bot_access and self.bot_access_until and self.bot_access_until > timezone.now())

    @property
    def bot_days_left(self) -> int:
        from django.utils import timezone
        if not self.bot_access_until:
            return 0
        return max(0, (self.bot_access_until - timezone.now()).days)

    def extend_bot_access(self, days: int) -> None:
        from datetime import timedelta
        from django.utils import timezone
        now = timezone.now()
        base = self.bot_access_until if (self.bot_access_until and self.bot_access_until > now) else now
        self.bot_access = True
        self.bot_access_granted = self.bot_access_granted or now
        self.bot_access_until = base + timedelta(days=days)
        self.save(update_fields=["bot_access", "bot_access_granted", "bot_access_until"])

    def expire_if_due(self) -> bool:
        """If bot access has ended: turn the flag off, revoke TradingView invite flag, pause the user's bot.
        Returns True when something was changed. Webhooks stop because api_tenants only lists active access."""
        from django.utils import timezone
        if not self.bot_access_until or self.bot_access_until > timezone.now():
            return False
        if not self.bot_access and not self.tv_access_granted:
            return False
        self.bot_access = False
        self.tv_access_granted = False
        self.save(update_fields=["bot_access", "tv_access_granted"])
        try:
            from bots.models import BotSettings
            BotSettings.objects.filter(user=self.user, enabled=True).update(enabled=False)
        except Exception:
            pass
        return True

    def add_credits(self, n: int) -> None:
        n = max(0, int(n))
        self.credits += n
        self.purchased += n
        self.save(update_fields=["credits", "purchased"])


class CreditLog(models.Model):
    """Every change to a customer's credits, for accounting."""
    profile = models.ForeignKey(Profile, on_delete=models.CASCADE, related_name="credit_log")
    delta = models.IntegerField()
    balance = models.IntegerField()
    reason = models.CharField(max_length=120)
    created = models.DateTimeField(auto_now_add=True)

    class Meta:
        ordering = ["-created"]
