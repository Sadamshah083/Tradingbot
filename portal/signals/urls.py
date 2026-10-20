from django.urls import path

from . import views

urlpatterns = [
    path("api/ingest/", views.api_ingest, name="api_ingest"),
    path("feed/", views.feed, name="signal_feed"),
    path("history/", views.history, name="signal_history"),
]
