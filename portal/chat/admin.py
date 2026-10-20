from django.contrib import admin

from .models import Message


@admin.register(Message)
class MessageAdmin(admin.ModelAdmin):
    list_display = ("created", "customer", "from_admin", "author", "read", "text")
    list_filter = ("from_admin", "read")
    search_fields = ("customer__username", "text")
