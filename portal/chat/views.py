import json

from django.contrib.auth import get_user_model
from django.contrib.auth.decorators import login_required, user_passes_test
from django.db.models import Count, Max, Q
from django.http import HttpResponseBadRequest, JsonResponse
from django.shortcuts import get_object_or_404, render
from django.views.decorators.http import require_GET, require_POST

from .models import Message

User = get_user_model()
staff_required = user_passes_test(lambda u: u.is_superuser, login_url="admin_login")


def _text_from(request) -> str:
    if request.content_type == "application/json":
        try:
            return str(json.loads(request.body.decode("utf-8")).get("text", "")).strip()
        except (json.JSONDecodeError, UnicodeDecodeError):
            return ""
    return request.POST.get("text", "").strip()


# Ã¢”â‚¬Ã¢”â‚¬ customer side Ã¢”â‚¬Ã¢”â‚¬Ã¢”â‚¬Ã¢”â‚¬Ã¢”â‚¬Ã¢”â‚¬Ã¢”â‚¬Ã¢”â‚¬Ã¢”â‚¬Ã¢”â‚¬Ã¢”â‚¬Ã¢”â‚¬Ã¢”â‚¬Ã¢”â‚¬Ã¢”â‚¬Ã¢”â‚¬Ã¢”â‚¬Ã¢”â‚¬Ã¢”â‚¬Ã¢”â‚¬Ã¢”â‚¬Ã¢”â‚¬Ã¢”â‚¬Ã¢”â‚¬Ã¢”â‚¬Ã¢”â‚¬Ã¢”â‚¬Ã¢”â‚¬Ã¢”â‚¬Ã¢”â‚¬Ã¢”â‚¬Ã¢”â‚¬Ã¢”â‚¬Ã¢”â‚¬Ã¢”â‚¬Ã¢”â‚¬Ã¢”â‚¬Ã¢”â‚¬Ã¢”â‚¬Ã¢”â‚¬Ã¢”â‚¬Ã¢”â‚¬Ã¢”â‚¬Ã¢”â‚¬Ã¢”â‚¬Ã¢”â‚¬Ã¢”â‚¬Ã¢”â‚¬Ã¢”â‚¬Ã¢”â‚¬Ã¢”â‚¬Ã¢”â‚¬Ã¢”â‚¬Ã¢”â‚¬Ã¢”â‚¬Ã¢”â‚¬Ã¢”â‚¬Ã¢”â‚¬Ã¢”â‚¬Ã¢”â‚¬Ã¢”â‚¬
@login_required
def room(request):
    msgs = Message.objects.filter(customer=request.user).select_related("author")
    Message.objects.filter(customer=request.user, from_admin=True, read=False).update(read=True)
    return render(request, "chat/room.html", {"messages_list": msgs, "last_id": msgs.last().id if msgs.exists() else 0})


@login_required
@require_GET
def poll(request):
    after = int(request.GET.get("after", 0) or 0)
    qs = Message.objects.filter(customer=request.user, id__gt=after).select_related("author")
    items = [m.as_dict() for m in qs]
    Message.objects.filter(customer=request.user, from_admin=True, read=False).update(read=True)
    return JsonResponse({"items": items})


@login_required
@require_POST
def send(request):
    text = _text_from(request)
    if not text:
        return HttpResponseBadRequest("empty message")
    m = Message.objects.create(customer=request.user, from_admin=False, author=request.user, text=text[:2000])
    return JsonResponse({"ok": True, "message": m.as_dict()})


# Ã¢”â‚¬Ã¢”â‚¬ staff side Ã¢”â‚¬Ã¢”â‚¬Ã¢”â‚¬Ã¢”â‚¬Ã¢”â‚¬Ã¢”â‚¬Ã¢”â‚¬Ã¢”â‚¬Ã¢”â‚¬Ã¢”â‚¬Ã¢”â‚¬Ã¢”â‚¬Ã¢”â‚¬Ã¢”â‚¬Ã¢”â‚¬Ã¢”â‚¬Ã¢”â‚¬Ã¢”â‚¬Ã¢”â‚¬Ã¢”â‚¬Ã¢”â‚¬Ã¢”â‚¬Ã¢”â‚¬Ã¢”â‚¬Ã¢”â‚¬Ã¢”â‚¬Ã¢”â‚¬Ã¢”â‚¬Ã¢”â‚¬Ã¢”â‚¬Ã¢”â‚¬Ã¢”â‚¬Ã¢”â‚¬Ã¢”â‚¬Ã¢”â‚¬Ã¢”â‚¬Ã¢”â‚¬Ã¢”â‚¬Ã¢”â‚¬Ã¢”â‚¬Ã¢”â‚¬Ã¢”â‚¬Ã¢”â‚¬Ã¢”â‚¬Ã¢”â‚¬Ã¢”â‚¬Ã¢”â‚¬Ã¢”â‚¬Ã¢”â‚¬Ã¢”â‚¬Ã¢”â‚¬Ã¢”â‚¬Ã¢”â‚¬Ã¢”â‚¬Ã¢”â‚¬Ã¢”â‚¬Ã¢”â‚¬Ã¢”â‚¬Ã¢”â‚¬Ã¢”â‚¬Ã¢”â‚¬Ã¢”â‚¬Ã¢”â‚¬Ã¢”â‚¬
@staff_required
def inbox(request):
    convs = (User.objects.filter(is_superuser=False, chat_messages__isnull=False).distinct()
             .annotate(unread=Count("chat_messages", filter=Q(chat_messages__from_admin=False, chat_messages__read=False)),
                       last=Max("chat_messages__created")).order_by("-unread", "-last"))
    rows = []
    for u in convs:
        last_msg = Message.objects.filter(customer=u).order_by("-created").first()
        rows.append({"user": u, "unread": u.unread, "last": last_msg})
    return render(request, "chat/inbox.html", {"rows": rows, "section": "inbox", "hide_nav": True})


@staff_required
def conversation(request, user_id):
    customer = get_object_or_404(User, pk=user_id, is_superuser=False)
    msgs = Message.objects.filter(customer=customer).select_related("author")
    Message.objects.filter(customer=customer, from_admin=False, read=False).update(read=True)
    return render(request, "chat/conversation.html", {"customer": customer, "messages_list": msgs, "last_id": msgs.last().id if msgs.exists() else 0,
                                                       "section": "inbox", "hide_nav": True})


@staff_required
@require_GET
def staff_poll(request, user_id):
    customer = get_object_or_404(User, pk=user_id, is_superuser=False)
    after = int(request.GET.get("after", 0) or 0)
    items = [m.as_dict() for m in Message.objects.filter(customer=customer, id__gt=after).select_related("author")]
    Message.objects.filter(customer=customer, from_admin=False, read=False).update(read=True)
    return JsonResponse({"items": items})


@staff_required
@require_POST
def staff_send(request, user_id):
    customer = get_object_or_404(User, pk=user_id, is_superuser=False)
    text = _text_from(request)
    if not text:
        return HttpResponseBadRequest("empty message")
    m = Message.objects.create(customer=customer, from_admin=True, author=request.user, text=text[:2000])
    return JsonResponse({"ok": True, "message": m.as_dict()})


@staff_required
@require_GET
def inbox_poll(request):
    """Badge counter for the staff header."""
    return JsonResponse({"unread": Message.objects.filter(from_admin=False, read=False).count()})

