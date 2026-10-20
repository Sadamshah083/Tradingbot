from django.urls import path

from . import views

urlpatterns = [
    path("", views.dashboard, name="bot_dashboard"),
    path("update/", views.update, name="bot_update"),
    path("status.json", views.api_status, name="bot_status_json"),
    path("staff/", views.staff_bots, name="staff_bots"),
    path("staff/<int:user_id>/action/", views.staff_bot_action, name="staff_bot_action"),
    # engine API (X-Webhook-Secret)
    path("api/tenants/", views.api_tenants, name="bot_api_tenants"),
    path("api/execution/", views.api_execution, name="bot_api_execution"),
    path("api/connection/", views.api_connection, name="bot_api_connection"),
]
