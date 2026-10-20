from django.conf import settings
from django.db import models


class Message(models.Model):
    """One chat line between a customer and the admin team. Each customer has one conversation."""
    customer = models.ForeignKey(settings.AUTH_USER_MODEL, on_delete=models.CASCADE, related_name="chat_messages")
    from_admin = models.BooleanField(default=False)
    author = models.ForeignKey(settings.AUTH_USER_MODEL, on_delete=models.SET_NULL, null=True, blank=True, related_name="+")
    text = models.TextField(max_length=2000)
    read = models.BooleanField(default=False, help_text="Read by the other side.")
    created = models.DateTimeField(auto_now_add=True)

    class Meta:
        ordering = ["created"]

    def as_dict(self) -> dict:
        return {"id": self.id, "from_admin": self.from_admin, "author": (self.author.username if self.author else ("Support" if self.from_admin else "You")),
                "text": self.text, "time": self.created.isoformat()}
