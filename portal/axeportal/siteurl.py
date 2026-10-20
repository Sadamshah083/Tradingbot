"""Absolute links are always built from settings.SITE_URL (the verified public address), never from the request's Host header."""
from django.conf import settings


def absolute_url(path: str = "/") -> str:
    return settings.SITE_URL.rstrip("/") + "/" + path.lstrip("/")
