from django.urls import path

from . import views

urlpatterns = [
    path("", views.index, name="blog"),
    path("staff/", views.staff_list, name="staff_blog"),
    path("staff/new/", views.staff_edit, name="staff_blog_new"),
    path("staff/<int:post_id>/", views.staff_edit, name="staff_blog_edit"),
    path("staff/<int:post_id>/delete/", views.staff_delete, name="staff_blog_delete"),
    path("category/<slug:slug>/", views.category, name="blog_category"),
    path("<slug:slug>/", views.post, name="blog_post"),
]
