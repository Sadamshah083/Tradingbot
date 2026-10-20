from django.urls import path

from . import views

urlpatterns = [
    path("", views.room, name="chat_room"),
    path("poll/", views.poll, name="chat_poll"),
    path("send/", views.send, name="chat_send"),
    path("inbox/", views.inbox, name="chat_inbox"),
    path("inbox/poll/", views.inbox_poll, name="chat_inbox_poll"),
    path("inbox/<int:user_id>/", views.conversation, name="chat_conversation"),
    path("inbox/<int:user_id>/poll/", views.staff_poll, name="chat_staff_poll"),
    path("inbox/<int:user_id>/send/", views.staff_send, name="chat_staff_send"),
]
