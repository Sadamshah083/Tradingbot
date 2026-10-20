from django.contrib import admin
from django.conf import settings
from django.urls import include, path, re_path
from django.views.static import serve
from django.views.generic import RedirectView

from accounts import staff
from accounts.views import AdminLoginView, landing, legal, robots_txt, site_page, sitemap_xml

SITE_SLUGS = [
    "how", "tradingview", "paper", "backtesting", "risk", "markets",
    "gold", "bitcoin", "binance", "mt5", "performance", "pricing",
    "strategy-lab", "about", "faq", "contact", "disclaimer",
]

def media(request, path):
    """Uploaded blog pictures (MEDIA_ROOT is read per request)."""
    return serve(request, path, document_root=settings.MEDIA_ROOT)


urlpatterns = [
    path("", landing, name="landing"),
    path("favicon.ico", RedirectView.as_view(url="/static/img/favicon.ico", permanent=True)),
    path("robots.txt", robots_txt, name="robots_txt"),
    path("sitemap.xml", sitemap_xml, name="sitemap_xml"),
    *[path(f"{slug}/", site_page, {"slug": slug}, name=f"site_{slug}") for slug in SITE_SLUGS],
    path("legal/<slug:kind>/", legal, name="legal"),
    path("admin/", RedirectView.as_view(pattern_name="staff_home", permanent=False)),
    path("admin/Dashboard", staff.home, name="staff_home"),                                   # canonical admin dashboard
    path("admin/Settings", staff.settings_page, name="staff_settings"),
    path("admin/Settings/team/", staff.team_action, name="staff_team_action"),
    path("admin/Dashboard/", RedirectView.as_view(pattern_name="staff_home", permanent=False)),
    path("admin/dashboard", RedirectView.as_view(pattern_name="staff_home", permanent=False)),  # lower-case spelling
    path("admin/login/", AdminLoginView.as_view(), name="admin_login"),
    path("accounts/", include("accounts.urls")),
    path("signals/", include("signals.urls")),
    path("chat/", include("chat.urls")),
    path("orders/", include("orders.urls")),
    path("blog/", include("blog.urls")),
    path("bot/", include("bots.urls")),
    re_path(r"^media/(?P<path>.*)$", media),
]
