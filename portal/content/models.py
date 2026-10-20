from django.conf import settings
from django.db import models


class Review(models.Model):
    """A customer review. Public only after staff approve it; one per customer."""
    STATUS = [("pending", "Pending"), ("approved", "Approved"), ("rejected", "Rejected")]
    user = models.OneToOneField(settings.AUTH_USER_MODEL, on_delete=models.CASCADE, related_name="review")
    display_name = models.CharField(max_length=40, help_text="Shown publicly. Never the e-mail address.")
    rating = models.PositiveSmallIntegerField()
    text = models.TextField(max_length=800)
    consent = models.BooleanField(default=False, help_text="The customer agreed to publish this review under the display name.")
    status = models.CharField(max_length=10, choices=STATUS, default="pending", db_index=True)
    created = models.DateTimeField(auto_now_add=True)
    decided_at = models.DateTimeField(null=True, blank=True)
    decided_by = models.ForeignKey(settings.AUTH_USER_MODEL, null=True, blank=True, on_delete=models.SET_NULL, related_name="+")

    class Meta:
        ordering = ["-created"]

    def __str__(self):
        return f"{self.display_name} {self.rating}/5 ({self.status})"

    @property
    def verified(self) -> bool:
        """Verified customer only when purchase records support it."""
        from orders.models import Order
        prof = getattr(self.user, "profile", None)
        return bool(Order.objects.filter(user=self.user, status="paid").exists() or (prof and prof.bot_access))


class ContactMessage(models.Model):
    """A message from the public contact form. Stored first; the e-mail notification is tracked separately."""
    EMAIL = [("pending", "Pending"), ("sent", "E-mail sent"), ("failed", "E-mail failed"), ("not_configured", "E-mail not configured")]
    name = models.CharField(max_length=80, blank=True)
    email = models.EmailField()
    subject = models.CharField(max_length=120, blank=True)
    message = models.TextField(max_length=3000)
    ip = models.GenericIPAddressField(null=True, blank=True)
    user_agent = models.CharField(max_length=200, blank=True)
    email_status = models.CharField(max_length=16, choices=EMAIL, default="pending")
    email_error = models.CharField(max_length=200, blank=True)
    handled = models.BooleanField(default=False)
    created = models.DateTimeField(auto_now_add=True)

    class Meta:
        ordering = ["-created"]

    def __str__(self):
        return f"{self.email}: {self.subject or self.message[:40]}"
