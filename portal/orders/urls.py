from django.urls import path

from . import views

urlpatterns = [
    path("checkout/<str:product>/", views.checkout, name="checkout"),
    path("stripe/<str:product>/start/", views.stripe_checkout, name="stripe_checkout"),
    path("stripe/success/", views.stripe_success, name="stripe_success"),
    path("stripe/webhook/", views.stripe_webhook, name="stripe_webhook"),
    path("download/bot/", views.download_bot, name="download_bot"),
    path("staff/", views.staff_orders, name="staff_orders"),
    path("staff/payments/", views.staff_payments, name="staff_payments"),
    path("staff/<int:order_id>/decide/", views.staff_order_decide, name="staff_order_decide"),
]
