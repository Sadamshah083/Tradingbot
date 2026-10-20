"""Django settings for the AxeAlgo customer portal (accounts, paid signals, live chat)."""
import hashlib
import os
import secrets
from pathlib import Path

from dotenv import load_dotenv

BASE_DIR = Path(__file__).resolve().parent.parent
load_dotenv(BASE_DIR / ".env")
load_dotenv(BASE_DIR.parent / "webhook_bot" / ".env", override=False)   # share WEBHOOK_SECRET / Telegram with the bot

# Persistent secret key (generated once) so sessions survive restarts.
_key_file = BASE_DIR / ".secret_key"
if os.getenv("DJANGO_SECRET_KEY"):
    SECRET_KEY = os.environ["DJANGO_SECRET_KEY"]
elif _key_file.exists():
    SECRET_KEY = _key_file.read_text().strip()
else:
    SECRET_KEY = secrets.token_urlsafe(48)
    _key_file.write_text(SECRET_KEY)

DEBUG = os.getenv("DJANGO_DEBUG", "true").lower() == "true"
ALLOWED_HOSTS = [h.strip() for h in os.getenv("ALLOWED_HOSTS", "*").split(",") if h.strip()]
CSRF_TRUSTED_ORIGINS = [o.strip() for o in os.getenv(
    "CSRF_TRUSTED_ORIGINS",
    "https://sambot.aktechsolutions.tech,https://sambot.immigrationhorizons.com,https://*.lhr.life,https://*.ngrok-free.app,https://*.ngrok.app,https://*.trycloudflare.com,http://localhost:8001,http://127.0.0.1:8001",
).split(",") if o.strip()]
SECURE_PROXY_SSL_HEADER = ("HTTP_X_FORWARDED_PROTO", "https")
USE_X_FORWARDED_HOST = True
# Production HTTPS (set FORCE_HTTPS=true on the server)
if os.getenv("FORCE_HTTPS", "false").lower() == "true":
    SECURE_SSL_REDIRECT = True
    SESSION_COOKIE_SECURE = True
    CSRF_COOKIE_SECURE = True
    SECURE_HSTS_SECONDS = 31536000
    SECURE_HSTS_INCLUDE_SUBDOMAINS = True
    SECURE_CONTENT_TYPE_NOSNIFF = True

# Shared with the webhook bot: the bot posts signals to /api/signals/ with this secret in a header.
WEBHOOK_SECRET = os.getenv("WEBHOOK_SECRET", "")
TELEGRAM_BOT_TOKEN = os.getenv("TELEGRAM_BOT_TOKEN", "")
SITE_NAME = os.getenv("SITE_NAME", "SamBot")
SITE_TAGLINE = os.getenv("SITE_TAGLINE", "Algorithmic trading, built on real data.")
PRICING_URL = os.getenv("PRICING_URL", "/pricing/")

# The ONLY account allowed on the admin side. `manage.py ensure_superadmin` promotes this e-mail and demotes everyone else.
SUPERADMIN_EMAIL = os.getenv("SUPERADMIN_EMAIL", "").strip().lower()

# Shop
PRICE_BOT = float(os.getenv("PRICE_BOT", "20"))            # price of bot access, USD, per BOT_ACCESS_DAYS
BOT_ACCESS_DAYS = int(os.getenv("BOT_ACCESS_DAYS", "30"))   # each payment adds this many days of bot access
TRADINGVIEW_STRATEGY_URL = os.getenv("TRADINGVIEW_STRATEGY_URL", "")   # public page of the invite-only strategy
PAGE_SIZE = int(os.getenv("PAGE_SIZE", "25"))
PRICE_SIGNAL = float(os.getenv("PRICE_SIGNAL", "1"))       # price per signal, USD
PACK_SIZE = int(os.getenv("PACK_SIZE", "20"))              # signals per pack
SUPPORT_EMAIL = os.getenv("SUPPORT_EMAIL", "")
# Transactional e-mail (contact form notifications). Leave EMAIL_HOST empty until a provider is configured: messages are
# still saved and shown to staff, and marked "E-mail not configured".
EMAIL_HOST = os.getenv("EMAIL_HOST", "")
EMAIL_PORT = int(os.getenv("EMAIL_PORT", "587"))
EMAIL_HOST_USER = os.getenv("EMAIL_HOST_USER", "")
EMAIL_HOST_PASSWORD = os.getenv("EMAIL_HOST_PASSWORD", "")
EMAIL_USE_TLS = os.getenv("EMAIL_USE_TLS", "true").lower() == "true"
EMAIL_TIMEOUT = 10
DEFAULT_FROM_EMAIL = os.getenv("DEFAULT_FROM_EMAIL", "")      # a sender address verified with the provider (never the visitor's)
EMAIL_BACKEND = "django.core.mail.backends.smtp.EmailBackend"
CONTACT_LIMIT_PER_HOUR = int(os.getenv("CONTACT_LIMIT_PER_HOUR", "3"))
# Search engines: only the canonical production host is indexable (set SEARCH_INDEXING=false on staging/preview).
SEARCH_INDEXING = os.getenv("SEARCH_INDEXING", "true").lower() == "true"
SITE_URL = os.getenv("SITE_URL", "https://sambot.aktechsolutions.tech").rstrip("/")
# Google Analytics 4 measurement ID, e.g. G-XXXXXXXXXX (leave empty to disable)
GA_MEASUREMENT_ID = os.getenv("GA_MEASUREMENT_ID", "").strip()
# Payment instructions shown on the checkout page (any that are empty are hidden)
PAYMENT_BANK = os.getenv("PAYMENT_BANK", "")               # e.g. "Meezan Bank, IBAN PK.., account name .."
PAYMENT_CRYPTO = os.getenv("PAYMENT_CRYPTO", "")           # e.g. "USDT (TRC20): T..."
PAYMENT_PAYPAL_LINK = os.getenv("PAYMENT_PAYPAL_LINK", "") # e.g. https://paypal.me/yourname/20
PAYMENT_STRIPE_LINK = os.getenv("PAYMENT_STRIPE_LINK", "") # Stripe / Gumroad / Lemon Squeezy checkout link
PACKAGE_ZIP = BASE_DIR / "dist" / "axealgo_package.zip"    # built by `manage.py build_package`
# Stripe card payments (leave empty to hide the card option). Test keys start with sk_test_ / pk_test_.
STRIPE_SECRET_KEY = os.getenv("STRIPE_SECRET_KEY", "")
STRIPE_PUBLISHABLE_KEY = os.getenv("STRIPE_PUBLISHABLE_KEY", "")
STRIPE_WEBHOOK_SECRET = os.getenv("STRIPE_WEBHOOK_SECRET", "")
STRIPE_ENABLED = bool(STRIPE_SECRET_KEY)
# The webhook bot's own HTTP API (webhook_bot/server.py); the admin side switches it on/off and places manual trades through it
BOT_URL = os.getenv("BOT_URL", "http://127.0.0.1:8000").rstrip("/")
MAX_SIGNALS_PER_ORDER = int(os.getenv("MAX_SIGNALS_PER_ORDER", "500"))

INSTALLED_APPS = [
    "django.contrib.admin",
    "django.contrib.auth",
    "django.contrib.contenttypes",
    "django.contrib.sessions",
    "django.contrib.messages",
    "django.contrib.staticfiles",
    "django.contrib.humanize",
    "accounts",
    "signals",
    "chat",
    "orders",
    "blog",
    "bots",
    "content",
]

MIDDLEWARE = [
    "django.middleware.security.SecurityMiddleware",
    "django.contrib.sessions.middleware.SessionMiddleware",
    "django.middleware.common.CommonMiddleware",
    "django.middleware.csrf.CsrfViewMiddleware",
    "django.contrib.auth.middleware.AuthenticationMiddleware",
    "accounts.jwtauth.JWTAuthMiddleware",
    "django.contrib.messages.middleware.MessageMiddleware",
    "django.middleware.clickjacking.XFrameOptionsMiddleware",
    "accounts.middleware.NoCacheAuthMiddleware",
    "accounts.middleware.NoIndexPreviewMiddleware",
]

ROOT_URLCONF = "axeportal.urls"
TEMPLATES = [{
    "BACKEND": "django.template.backends.django.DjangoTemplates",
    "DIRS": [BASE_DIR / "templates"],
    "APP_DIRS": True,
    "OPTIONS": {"context_processors": [
        "django.template.context_processors.request",
        "django.contrib.auth.context_processors.auth",
        "django.contrib.messages.context_processors.messages",
        "accounts.context_processors.site",
    ]},
}]
WSGI_APPLICATION = "axeportal.wsgi.application"

DATABASES = {"default": {"ENGINE": "django.db.backends.sqlite3", "NAME": BASE_DIR / "db.sqlite3"}}

AUTH_PASSWORD_VALIDATORS = [
    {"NAME": "django.contrib.auth.password_validation.UserAttributeSimilarityValidator"},
    {"NAME": "django.contrib.auth.password_validation.MinimumLengthValidator", "OPTIONS": {"min_length": 8}},
    {"NAME": "django.contrib.auth.password_validation.CommonPasswordValidator"},
]
# Signals: how long a "signal" event stays actionable, and how fresh an MT5 bridge heartbeat must be to count as live.
SIGNAL_TTL_MINUTES = int(os.getenv("SIGNAL_TTL_MINUTES", "90"))
MT5_HEARTBEAT_FRESH_SECONDS = int(os.getenv("MT5_HEARTBEAT_FRESH_SECONDS", "90"))    # newer than this: live
MT5_HEARTBEAT_STALE_SECONDS = int(os.getenv("MT5_HEARTBEAT_STALE_SECONDS", "300"))   # older than this: disconnected
LOGIN_URL = "login"
LOGIN_REDIRECT_URL = "dashboard"
LOGOUT_REDIRECT_URL = "landing"
# Login tokens (see accounts/jwtauth.py). JWT_SECRET must be set in .env; the fallback is derived from SECRET_KEY.
JWT_EXPIRE_HOURS = int(os.getenv("JWT_EXPIRE_HOURS", "24"))
JWT_SECRET = os.getenv("JWT_SECRET") or hashlib.sha256(("jwt:" + SECRET_KEY).encode()).hexdigest()
SESSION_COOKIE_AGE = JWT_EXPIRE_HOURS * 3600
# After logout / back-button: never serve cached authenticated pages
SESSION_EXPIRE_AT_BROWSER_CLOSE = False

LANGUAGE_CODE = "en-us"
TIME_ZONE = os.getenv("TIME_ZONE", "Asia/Karachi")
USE_I18N = True
USE_TZ = True

STATIC_URL = "static/"
STATICFILES_DIRS = [BASE_DIR / "static"]   # logo, backtests.json for the homepage charts
MEDIA_URL = "/media/"
MEDIA_ROOT = Path(os.getenv("MEDIA_ROOT", BASE_DIR / "media"))   # blog pictures uploaded from the admin
DATA_UPLOAD_MAX_MEMORY_SIZE = 8 * 1024 * 1024
STATIC_ROOT = Path(os.getenv("STATIC_ROOT", BASE_DIR / "staticfiles"))   # on a server: a folder nginx can read, e.g. /var/www/axealgo/static
DEFAULT_AUTO_FIELD = "django.db.models.BigAutoField"
