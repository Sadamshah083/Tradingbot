from django.urls import path

from . import staff, views

urlpatterns = [
    path("login/", views.CustomerLoginView.as_view(), name="login"),
    path("logout/", views.CustomerLogoutView.as_view(), name="logout"),
    path("register/", views.register, name="register"),
    path("dashboard/", views.dashboard, name="dashboard"),
    path("settings/", views.account_settings, name="account_settings"),
    # admin side (superadmin only)
    path("staff/", staff.entry, name="staff_entry"),   # old URL: forwards to the canonical /admin/Dashboard
    path("staff/bot/mode/", staff.bot_mode, name="staff_bot_mode"),
    path("staff/customers/", staff.customers_moved, name="staff_customers"),   # customers now live under Leads
    path("staff/leads/", staff.leads, name="staff_leads"),
    path("staff/leads/<int:user_id>/update/", staff.lead_update, name="staff_lead_update"),
    path("staff/customers/<int:user_id>/update/", staff.customer_update, name="staff_customer_update"),
    path("staff/signals/", staff.signals, name="staff_signals"),
    path("staff/signals/new/", staff.signal_create, name="staff_signal_create"),
    path("staff/signals/<int:signal_id>/close/", staff.signal_close, name="staff_signal_close"),
    path("staff/manual/", staff.manual, name="staff_manual"),
    path("staff/bot/", staff.bot, name="staff_bot"),
]
