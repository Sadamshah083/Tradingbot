"""Who may do what.

- superadmin: the single User with is_superuser (SUPERADMIN_EMAIL). Full access, and the only one who can assign roles.
- admin:      Profile.role == "admin". Customers, signals, manual orders and the chat inbox.
- agent:      Profile.role == "agent". The chat inbox only.
- customer:   everyone else.
Staff roles live in Profile.role and never grant Django's is_staff / is_superuser.
"""
from functools import wraps

from django.contrib.auth.views import redirect_to_login
from django.core.exceptions import PermissionDenied
from django.urls import reverse

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


def _guard(test):
    """Decorator factory: anonymous visitors go to the team login and come back afterwards; signed-in users without the
    right role get a 403 (so they never bounce between pages)."""
    def decorator(view):
        @wraps(view)
        def wrapper(request, *args, **kwargs):
            if not request.user.is_authenticated:
                return redirect_to_login(request.get_full_path(), login_url=reverse("admin_login"))
            if not test(request.user):
                raise PermissionDenied
            return view(request, *args, **kwargs)
        return wrapper
    return decorator


superadmin_required = _guard(is_superadmin)
admin_required = _guard(is_admin_staff)
chat_staff_required = _guard(is_chat_staff)
