from django.urls import path

from . import views

urlpatterns = [
    path("review/", views.review_new, name="review_new"),
]
