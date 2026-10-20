from django.contrib import admin

from .models import BotEvent, BotSettings, BrokerConnection, Execution


@admin.register(BotSettings)
class BotSettingsAdmin(admin.ModelAdmin):
    list_display = ("user", "enabled", "kill_switch", "mode", "broker", "markets", "timeframes", "risk_pct")
    list_filter = ("enabled", "mode", "broker")
    readonly_fields = ("webhook_token",)


@admin.register(BrokerConnection)
class BrokerConnectionAdmin(admin.ModelAdmin):
    list_display = ("user", "broker", "status", "balance", "last_checked")
    exclude = ("api_key_enc", "api_secret_enc", "extra_enc")   # never show secrets, even encrypted


@admin.register(Execution)
class ExecutionAdmin(admin.ModelAdmin):
    list_display = ("user", "symbol", "side", "mode", "broker", "qty", "entry", "sl", "tp", "status", "pnl", "opened_at")
    list_filter = ("status", "mode", "broker", "symbol")


admin.site.register(BotEvent)
