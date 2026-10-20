"""Login tokens: a signed JWT (HS256) is issued at login and enforced by middleware.

- Secret and lifetime come from .env: JWT_SECRET and JWT_EXPIRE_HOURS (default 24).
- The token travels in an HttpOnly cookie (and a `Authorization: Bearer` header is also accepted).
- Expiry is fixed from the moment of login (no sliding window): after JWT_EXPIRE_HOURS the user must log in again.
- Implemented with the standard library (hmac/hashlib) so no extra package is needed.
"""
import base64
import hashlib
import hmac
import json
import time
import uuid

from django.conf import settings
from django.contrib.auth import get_user_model, login, logout
from django.contrib.auth.signals import user_logged_in, user_logged_out
from django.dispatch import receiver

COOKIE_NAME = "sambot_jwt"
ISSUER = "sambot"


def _b64e(raw: bytes) -> str:
    return base64.urlsafe_b64encode(raw).rstrip(b"=").decode()


def _b64d(text: str) -> bytes:
    return base64.urlsafe_b64decode(text + "=" * (-len(text) % 4))


def _sign(signing_input: bytes) -> str:
    return _b64e(hmac.new(settings.JWT_SECRET.encode(), signing_input, hashlib.sha256).digest())


def issue_token(user, now=None) -> str:
    now = int(now if now is not None else time.time())
    header = {"alg": "HS256", "typ": "JWT"}
    payload = {
        "iss": ISSUER, "sub": str(user.pk), "iat": now,
        "exp": now + settings.JWT_EXPIRE_HOURS * 3600, "jti": uuid.uuid4().hex,
    }
    signing_input = (_b64e(json.dumps(header, separators=(",", ":")).encode()) + "."
                     + _b64e(json.dumps(payload, separators=(",", ":")).encode())).encode()
    return signing_input.decode() + "." + _sign(signing_input)


def decode_token(token, now=None):
    """Return the payload dict, or None if the token is malformed, tampered with or expired."""
    try:
        head_b64, payload_b64, sig = token.split(".")
        header = json.loads(_b64d(head_b64))
        if header.get("alg") != "HS256":          # never trust the token's own algorithm choice
            return None
        if not hmac.compare_digest(sig, _sign((head_b64 + "." + payload_b64).encode())):
            return None
        payload = json.loads(_b64d(payload_b64))
        if payload.get("iss") != ISSUER or int(payload["exp"]) <= int(now if now is not None else time.time()):
            return None
        return payload
    except Exception:
        return None


def _user_from_payload(payload):
    try:
        user = get_user_model().objects.get(pk=int(payload["sub"]))
    except Exception:
        return None
    return user if user.is_active else None


@receiver(user_logged_in)
def _flag_issue(sender, request, user, **kwargs):
    if request is not None and not getattr(request, "_jwt_restoring", False):
        request._jwt_issue_for = user
        from .roles import role_of
        if role_of(user) == "customer" and hasattr(request, "session"):
            request.session["open_chat_popup"] = True   # the chat panel opens once after login


@receiver(user_logged_out)
def _flag_clear(sender, request, user, **kwargs):
    if request is not None:
        request._jwt_clear = True


class JWTAuthMiddleware:
    """Must sit after AuthenticationMiddleware."""

    def __init__(self, get_response):
        self.get_response = get_response

    def __call__(self, request):
        token = request.COOKIES.get(COOKIE_NAME, "")
        header = request.META.get("HTTP_AUTHORIZATION", "")
        if header.lower().startswith("bearer "):
            token = header[7:].strip()
        payload = decode_token(token) if token else None

        if request.user.is_authenticated:
            # The session alone is not enough: it must be backed by a valid, unexpired token for the same user.
            if payload is None or payload.get("sub") != str(request.user.pk):
                logout(request)
                request._jwt_clear = True
        elif payload is not None:
            user = _user_from_payload(payload)
            if user is not None:
                request._jwt_restoring = True
                login(request, user, backend="django.contrib.auth.backends.ModelBackend")

        response = self.get_response(request)

        user = getattr(request, "_jwt_issue_for", None)
        if user is not None:
            response.set_cookie(
                COOKIE_NAME, issue_token(user), max_age=settings.JWT_EXPIRE_HOURS * 3600,
                httponly=True, samesite="Lax", secure=bool(getattr(settings, "SESSION_COOKIE_SECURE", False)),
            )
        elif getattr(request, "_jwt_clear", False):
            response.delete_cookie(COOKIE_NAME)
        return response
