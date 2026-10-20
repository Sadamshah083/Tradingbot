from django.contrib import admin

from .models import CreditLog, Profile


@admin.register(Profile)
class ProfileAdmin(admin.ModelAdmin):
    list_display = ("user", "credits", "purchased", "used", "active", "telegram_chat_id", "created")
    list_filter = ("active",)
    search_fields = ("user__username", "user__email", "telegram_chat_id")


@admin.register(CreditLog)
class CreditLogAdmin(admin.ModelAdmin):
    list_display = ("profile", "delta", "balance", "reason", "created")
