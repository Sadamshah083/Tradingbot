import json

from django.contrib.auth import get_user_model
from django.contrib.auth.decorators import login_required, user_passes_test
from django.db.models import Count, Max, Q
from django.http import HttpResponseBadRequest, JsonResponse
from django.shortcuts import get_object_or_404, render
from django.views.decorators.http import require_GET, require_POST

from django.utils import timezone

from .models import Message

User = get_user_model()
from accounts.roles import chat_staff_required as staff_required, role_of  # noqa: E402



ONLINE_WINDOW_SECONDS = 90
AUTO_REPLY_COOLDOWN_MINUTES = 30


def _customers():
    """Chat conversations belong to customers only (not to the team)."""
    return User.objects.filter(is_superuser=False).exclude(profile__role__in=["agent", "admin"])


def agents_online() -> bool:
    """True when a team member has had the inbox open in the last minute or two."""
    from accounts.models import Profile
    since = timezone.now() - timezone.timedelta(seconds=ONLINE_WINDOW_SECONDS)
    return Profile.objects.filter(last_seen__gt=since).filter(Q(role__in=["agent", "admin"]) | Q(user__is_superuser=True)).exists()


def _touch(user):
    """Remember that this team member is around (throttled to one write every 20 s)."""
    from accounts.models import Profile
    profile, _ = Profile.objects.get_or_create(user=user)
    now = timezone.now()
    if not profile.last_seen or (now - profile.last_seen).total_seconds() > 20:
        profile.last_seen = now
        profile.save(update_fields=["last_seen"])


def _auto_ack(customer):
    """The team answers 24/7 but may be away: acknowledge a customer once per cooldown so nobody is left wondering."""
    since = timezone.now() - timezone.timedelta(minutes=AUTO_REPLY_COOLDOWN_MINUTES)
    if Message.objects.filter(customer=customer, from_admin=True, created__gt=since).exists():
        return
    text = ("Thanks, your message is in. An agent is online and will reply here shortly." if agents_online() else
            "Thanks, we have your message. Support runs 24/7 and an agent will reply here as soon as one is online. "
            "You do not need to stay on this page; replies also show in your menu.")
    Message.objects.create(customer=customer, from_admin=True, author=None, auto=True, text=text)


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
    return render(request, "chat/room.html", {"messages_list": msgs, "last_id": msgs.last().id if msgs.exists() else 0, "agents_online": agents_online()})


@login_required
@require_GET
def poll(request):
    after = int(request.GET.get("after", 0) or 0)
    qs = Message.objects.filter(customer=request.user, id__gt=after).select_related("author")
    items = [m.as_dict() for m in qs]
    Message.objects.filter(customer=request.user, from_admin=True, read=False).update(read=True)
    return JsonResponse({"items": items, "agents_online": agents_online()})


@login_required
@require_GET
def unread(request):
    """Badge counter for the floating chat button."""
    return JsonResponse({"unread": Message.objects.filter(customer=request.user, from_admin=True, read=False).count()})


@login_required
@require_POST
def send(request):
    text = _text_from(request)
    if not text:
        return HttpResponseBadRequest("empty message")
    m = Message.objects.create(customer=request.user, from_admin=False, author=request.user, text=text[:2000])
    _auto_ack(request.user)
    return JsonResponse({"ok": True, "message": m.as_dict()})


# Ã¢”â‚¬Ã¢”â‚¬ staff side Ã¢”â‚¬Ã¢”â‚¬Ã¢”â‚¬Ã¢”â‚¬Ã¢”â‚¬Ã¢”â‚¬Ã¢”â‚¬Ã¢”â‚¬Ã¢”â‚¬Ã¢”â‚¬Ã¢”â‚¬Ã¢”â‚¬Ã¢”â‚¬Ã¢”â‚¬Ã¢”â‚¬Ã¢”â‚¬Ã¢”â‚¬Ã¢”â‚¬Ã¢”â‚¬Ã¢”â‚¬Ã¢”â‚¬Ã¢”â‚¬Ã¢”â‚¬Ã¢”â‚¬Ã¢”â‚¬Ã¢”â‚¬Ã¢”â‚¬Ã¢”â‚¬Ã¢”â‚¬Ã¢”â‚¬Ã¢”â‚¬Ã¢”â‚¬Ã¢”â‚¬Ã¢”â‚¬Ã¢”â‚¬Ã¢”â‚¬Ã¢”â‚¬Ã¢”â‚¬Ã¢”â‚¬Ã¢”â‚¬Ã¢”â‚¬Ã¢”â‚¬Ã¢”â‚¬Ã¢”â‚¬Ã¢”â‚¬Ã¢”â‚¬Ã¢”â‚¬Ã¢”â‚¬Ã¢”â‚¬Ã¢”â‚¬Ã¢”â‚¬Ã¢”â‚¬Ã¢”â‚¬Ã¢”â‚¬Ã¢”â‚¬Ã¢”â‚¬Ã¢”â‚¬Ã¢”â‚¬Ã¢”â‚¬Ã¢”â‚¬Ã¢”â‚¬Ã¢”â‚¬Ã¢”â‚¬Ã¢”â‚¬
@staff_required
def inbox(request):
    _touch(request.user)
    selected = request.GET.get("u", "")
    return render(request, "chat/inbox.html", {"selected": int(selected) if selected.isdigit() else 0, "section": "inbox", "hide_nav": True})


@staff_required
@require_GET
def inbox_list(request):
    """Conversation list for the console (unread first). Polled every few seconds."""
    _touch(request.user)
    q = request.GET.get("q", "").strip()
    convs = (_customers().filter(chat_messages__isnull=False).distinct().select_related("profile")
             .annotate(unread=Count("chat_messages", filter=Q(chat_messages__from_admin=False, chat_messages__read=False), distinct=True),
                       last=Max("chat_messages__created")).order_by("-unread", "-last"))
    if q:
        convs = convs.filter(Q(username__icontains=q) | Q(email__icontains=q))
    rows = []
    for u in convs[:200]:
        last = Message.objects.filter(customer=u).order_by("-created").first()
        prof = getattr(u, "profile", None)
        rows.append({
            "id": u.id, "name": u.email or u.username, "username": u.username, "unread": u.unread,
            "text": last.text[:90] if last else "", "mine": bool(last and last.from_admin), "time": last.created.isoformat() if last else "",
            "lead": prof.lead_status if prof else "new", "credits": prof.credits if prof else 0,
            "bot": bool(prof and prof.bot_active_access), "joined": u.date_joined.isoformat(),
        })
    return JsonResponse({"rows": rows, "unread_total": Message.objects.filter(from_admin=False, read=False).count()})


@staff_required
def conversation(request, user_id):
    """Kept for old links: open the console on that customer."""
    from django.shortcuts import redirect
    from django.urls import reverse
    return redirect(f"{reverse('chat_inbox')}?u={int(user_id)}")


@staff_required
@require_GET
def staff_poll(request, user_id):
    _touch(request.user)
    customer = get_object_or_404(_customers(), pk=user_id)
    after = int(request.GET.get("after", 0) or 0)
    items = [m.as_dict() for m in Message.objects.filter(customer=customer, id__gt=after).select_related("author")]
    Message.objects.filter(customer=customer, from_admin=False, read=False).update(read=True)
    return JsonResponse({"items": items})


@staff_required
@require_POST
def staff_send(request, user_id):
    customer = get_object_or_404(_customers(), pk=user_id)
    text = _text_from(request)
    if not text:
        return HttpResponseBadRequest("empty message")
    m = Message.objects.create(customer=customer, from_admin=True, author=request.user, text=text[:2000])
    return JsonResponse({"ok": True, "message": m.as_dict()})


@staff_required
@require_GET
def inbox_poll(request):
    """Badge counter for the staff header (also tells customers a team member is around)."""
    _touch(request.user)
    return JsonResponse({"unread": Message.objects.filter(from_admin=False, read=False).count()})

