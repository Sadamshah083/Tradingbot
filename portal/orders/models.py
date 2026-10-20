from django.conf import settings
from django.db import models


class Order(models.Model):
    PRODUCTS = [("bot", "Bot package"), ("signals", "Signal pack")]
    METHODS = [("bank", "Bank transfer"), ("crypto", "Crypto (USDT)"), ("paypal", "PayPal"), ("card", "Card / Stripe link"), ("other", "Other")]
    STATUS = [("pending", "Pending confirmation"), ("paid", "Paid & delivered"), ("rejected", "Rejected")]

    user = models.ForeignKey(settings.AUTH_USER_MODEL, on_delete=models.CASCADE, related_name="orders")
    product = models.CharField(max_length=16, choices=PRODUCTS)
    quantity = models.PositiveIntegerField(default=1, help_text="Signal credits for a pack, 1 for the bot.")
    amount_usd = models.DecimalField(max_digits=8, decimal_places=2)
    method = models.CharField(max_length=16, choices=METHODS, default="bank")
    reference = models.CharField(max_length=120, help_text="Transaction id / sender name the customer gives us.")
    note = models.CharField(max_length=300, blank=True)
    status = models.CharField(max_length=12, choices=STATUS, default="pending")
    created = models.DateTimeField(auto_now_add=True)
    decided = models.DateTimeField(null=True, blank=True)
    decided_by = models.ForeignKey(settings.AUTH_USER_MODEL, null=True, blank=True, on_delete=models.SET_NULL, related_name="+")
    # Stripe (card payments)
    stripe_session_id = models.CharField(max_length=120, blank=True, db_index=True)
    stripe_payment_intent = models.CharField(max_length=120, blank=True)
    stripe_status = models.CharField(max_length=32, blank=True, help_text="Last status Stripe reported: open, complete, expired, paid, failed...")
    receipt_url = models.URLField(blank=True)

    class Meta:
        ordering = ["-created"]

    def __str__(self):
        return f"#{self.id} {self.user.username} {self.get_product_display()} ${self.amount_usd} ({self.status})"

    @property
    def title(self):
        return "Bot access (30 days)" if self.product == "bot" else f"{self.quantity} signal credit{'s' if self.quantity != 1 else ''}"
