"""Stop browsers from restoring authenticated pages after logout via the Back button."""


class NoCacheAuthMiddleware:
    def __init__(self, get_response):
        self.get_response = get_response

    def __call__(self, request):
        response = self.get_response(request)
        user = getattr(request, "user", None)
        if user is not None and user.is_authenticated:
            response["Cache-Control"] = "no-store, no-cache, must-revalidate, max-age=0"
            response["Pragma"] = "no-cache"
            response["Expires"] = "0"
        return response


class NoIndexPreviewMiddleware:
    """Keep staging, preview and alias hosts out of search results: only the configured production host is indexable."""

    def __init__(self, get_response):
        self.get_response = get_response

    def __call__(self, request):
        from urllib.parse import urlparse

        from django.conf import settings
        response = self.get_response(request)
        host = request.get_host().split(":")[0].lower()
        canonical = (urlparse(settings.SITE_URL).hostname or "").lower()
        if not settings.SEARCH_INDEXING or (canonical and host != canonical):
            response["X-Robots-Tag"] = "noindex, nofollow"
        return response
