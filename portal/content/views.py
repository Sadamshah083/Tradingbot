import logging
import re
from datetime import timedelta

from django.conf import settings
from django.contrib import messages
from django.contrib.auth.decorators import login_required
from django.core.mail import EmailMessage
from django.core.paginator import Paginator
from django.shortcuts import get_object_or_404, redirect, render
from django.utils import timezone
from django.views.decorators.http import require_POST

from accounts.roles import admin_required

from .models import ContactMessage, Review

log = logging.getLogger("portal.content")
EMAIL_RE = re.compile(r"^[^@\s]+@[^@\s]+\.[^@\s]+$")
TAGS_RE = re.compile(r"<[^>]*>")


def clean(text: str) -> str:
    """Plain text only: tags removed, whitespace normalised."""
    return re.sub(r"[ \t]+", " ", TAGS_RE.sub("", text or "")).strip()


def client_ip(request) -> str | None:
    fwd = request.META.get("HTTP_X_FORWARDED_FOR", "")
    ip = (fwd.split(",")[0].strip() if fwd else request.META.get("REMOTE_ADDR", "")) or None
    return ip[:45] if ip else None


# -- contact form --------------------------------------------------------------------------
def handle_contact(request) -> dict:
    """Process the contact form. Returns template context: values, errors, sent (True only once the message is saved)."""
    ctx = {"values": {}, "errors": {}, "sent": False}
    if request.method != "POST":
        return ctx
    p = request.POST
    values = {"name": clean(p.get("name", ""))[:80], "email": p.get("email", "").strip()[:254], "subject": clean(p.get("subject", ""))[:120], "message": clean(p.get("message", ""))}
    ctx["values"] = values
    if p.get("website"):                                   # honeypot: real visitors never see or fill this field
        ctx["sent"] = True
        return ctx
    errors = {}
    if not values["email"]:
        errors["email"] = "Enter your e-mail address so we can reply."
    elif not EMAIL_RE.match(values["email"]):
        errors["email"] = "That does not look like a valid e-mail address."
    if not values["message"]:
        errors["message"] = "Write a message so we know how to help."
    elif len(values["message"]) < 10:
        errors["message"] = "Please write a little more (at least 10 characters)."
    elif len(values["message"]) > 3000:
        errors["message"] = "Please keep the message under 3000 characters."
    ip = client_ip(request)
    if not errors and ip:
        recent = ContactMessage.objects.filter(ip=ip, created__gte=timezone.now() - timedelta(hours=1)).count()
        if recent >= settings.CONTACT_LIMIT_PER_HOUR:
            errors["form"] = "You have sent several messages recently. Please wait a while before sending another."
    if errors:
        ctx["errors"] = errors
        return ctx
    msg = ContactMessage.objects.create(name=values["name"], email=values["email"], subject=values["subject"], message=values["message"],
                                        ip=ip, user_agent=request.META.get("HTTP_USER_AGENT", "")[:200])
    notify(msg)
    ctx["sent"] = True
    ctx["values"] = {}
    return ctx


def notify(msg: ContactMessage) -> None:
    """E-mail the support inbox. The message is already saved; this only records how the notification went."""
    if not (settings.EMAIL_HOST and settings.SUPPORT_EMAIL and settings.DEFAULT_FROM_EMAIL):
        msg.email_status, msg.email_error = "not_configured", "EMAIL_HOST, SUPPORT_EMAIL or DEFAULT_FROM_EMAIL is not set"
    else:
        try:
            body = f"From: {msg.name or '(no name)'} <{msg.email}>\nSubject: {msg.subject or '(none)'}\nReceived: {msg.created:%Y-%m-%d %H:%M} UTC\n\n{msg.message}\n"
            EmailMessage(subject=f"[SamBot contact] {msg.subject or 'New message'}"[:150], body=body, from_email=settings.DEFAULT_FROM_EMAIL,
                         to=[settings.SUPPORT_EMAIL], reply_to=[msg.email]).send(fail_silently=False)
            msg.email_status, msg.email_error = "sent", ""
        except Exception as exc:
            log.warning("contact e-mail failed: %s", exc)
            msg.email_status, msg.email_error = "failed", str(exc)[:200]
    msg.save(update_fields=["email_status", "email_error"])


# -- reviews -------------------------------------------------------------------------------
@login_required
def review_new(request):
    existing = Review.objects.filter(user=request.user).first()
    errors, values = {}, {"display_name": request.user.first_name or "", "rating": "", "text": "", "consent": ""}
    if existing is None and request.method == "POST":
        p = request.POST
        values = {"display_name": clean(p.get("display_name", ""))[:40], "rating": p.get("rating", ""), "text": clean(p.get("text", "")), "consent": p.get("consent", "")}
        if len(values["display_name"]) < 2 or "@" in values["display_name"]:
            errors["display_name"] = "Choose a display name of at least 2 characters (not an e-mail address)."
        if values["rating"] not in ("1", "2", "3", "4", "5"):
            errors["rating"] = "Choose a rating from 1 to 5."
        if len(values["text"]) < 20:
            errors["text"] = "Please write at least 20 characters about your experience."
        elif len(values["text"]) > 800:
            errors["text"] = "Please keep it under 800 characters."
        if values["consent"] != "on":
            errors["consent"] = "Please confirm that we may publish your review under this name."
        if not errors:
            Review.objects.create(user=request.user, display_name=values["display_name"], rating=int(values["rating"]), text=values["text"], consent=True)
            messages.success(request, "Thank you. Your review was submitted and will appear on the website after our team approves it.")
            return redirect("review_new")
    return render(request, "content/review_new.html", {"existing": existing, "errors": errors, "values": values, "noindex": True})


# -- staff -----------------------------------------------------------------------------------
@admin_required
def staff_reviews(request):
    flt = request.GET.get("status", "pending")
    qs = Review.objects.select_related("user")
    if flt in ("pending", "approved", "rejected"):
        qs = qs.filter(status=flt)
    page = Paginator(qs, 15).get_page(request.GET.get("page"))
    counts = {k: Review.objects.filter(status=k).count() for k in ("pending", "approved", "rejected")}
    for r in page:
        r.is_verified = r.verified
    return render(request, "staff/reviews.html", {"reviews": page, "page": page, "flt": flt, "counts": counts, "section": "reviews", "hide_nav": True, "qs": f"status={flt}&"})


@admin_required
@require_POST
def staff_review_action(request, review_id):
    r = get_object_or_404(Review, pk=review_id)
    action = request.POST.get("action")
    if action in ("approve", "reject"):
        r.status = "approved" if action == "approve" else "rejected"
        r.decided_at, r.decided_by = timezone.now(), request.user
        r.save(update_fields=["status", "decided_at", "decided_by"])
        messages.success(request, f"Review by {r.display_name} {r.status}.")
    elif action == "delete":
        r.delete()
        messages.warning(request, "Review deleted.")
    return redirect(request.POST.get("next") or "staff_reviews")


@admin_required
def staff_messages(request):
    qs = ContactMessage.objects.all()
    page = Paginator(qs, 15).get_page(request.GET.get("page"))
    return render(request, "staff/messages.html", {"items": page, "page": page, "section": "messages", "hide_nav": True, "qs": "",
                                                   "unhandled": ContactMessage.objects.filter(handled=False).count()})


@admin_required
@require_POST
def staff_message_action(request, message_id):
    m = get_object_or_404(ContactMessage, pk=message_id)
    if request.POST.get("action") == "handled":
        m.handled = not m.handled
        m.save(update_fields=["handled"])
    return redirect(request.POST.get("next") or "staff_messages")
