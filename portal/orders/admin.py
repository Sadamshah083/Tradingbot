from django.contrib import admin

from .models import Order


@admin.register(Order)
class OrderAdmin(admin.ModelAdmin):
    list_display = ("id", "created", "user", "product", "quantity", "amount_usd", "method", "reference", "status", "decided")
    list_filter = ("status", "product", "method")
    search_fields = ("user__username", "user__email", "reference")
