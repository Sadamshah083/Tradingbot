from django.contrib import admin

from .models import Signal, SignalDelivery


@admin.register(Signal)
class SignalAdmin(admin.ModelAdmin):
    list_display = ("created", "event", "side", "symbol", "timeframe", "price", "sl", "tp2", "reason")
    list_filter = ("event", "symbol", "timeframe")
    search_fields = ("symbol", "external_id")


@admin.register(SignalDelivery)
class SignalDeliveryAdmin(admin.ModelAdmin):
    list_display = ("created", "signal", "user", "charged", "credits_after", "telegram_sent")
    list_filter = ("charged", "telegram_sent")
