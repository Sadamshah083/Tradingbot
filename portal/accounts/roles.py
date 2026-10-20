"""Who may do what.

- superadmin: the single User with is_superuser (SUPERADMIN_EMAIL). Full access, and the only one who can assign roles.
- admin:      Profile.role == "admin". Customers, signals, manual orders and the chat inbox.
- agent:      Profile.role == "agent". The chat inbox only.
- customer:   everyone else.
Staff roles live in Profile.role and never grant Django's is_staff / is_superuser.
"""
from django.contrib.auth.decorators import user_passes_test

ROLE_CHOICES = [("customer", "Customer"), ("agent", "Agent"), ("admin", "Admin")]


def role_of(user) -> str:
    if not getattr(user, "is_authenticated", False):
        return "anonymous"
    if user.is_superuser:
        return "superadmin"
    profile = getattr(user, "profile", None)
    return profile.role if profile is not None and profile.role in ("agent", "admin") else "customer"


def is_superadmin(user) -> bool:
    return role_of(user) == "superadmin"


def is_admin_staff(user) -> bool:
    return role_of(user) in ("superadmin", "admin")


def is_chat_staff(user) -> bool:
    return role_of(user) in ("superadmin", "admin", "agent")


def staff_home_name(user):
    """URL name of the landing page for a staff member, or None for customers."""
    return {"superadmin": "staff_home", "admin": "staff_home", "agent": "chat_inbox"}.get(role_of(user))


superadmin_required = user_passes_test(is_superadmin, login_url="admin_login")
admin_required = user_passes_test(is_admin_staff, login_url="admin_login")
chat_staff_required = user_passes_test(is_chat_staff, login_url="admin_login")
