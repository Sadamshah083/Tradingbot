from django.contrib import messages
from django.contrib.auth.decorators import user_passes_test
from django.core.paginator import Paginator
from django.db.models import F, Q
from django.http import Http404
from django.shortcuts import get_object_or_404, redirect, render
from django.utils import timezone
from django.views.decorators.http import require_POST

from .models import Category, Post

staff_required = user_passes_test(lambda u: u.is_superuser, login_url="admin_login")


# â”€â”€ public â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€
def index(request):
    qs = Post.objects.filter(published=True).select_related("category")
    cat = request.GET.get("category")
    q = request.GET.get("q", "").strip()
    if cat:
        qs = qs.filter(category__slug=cat)
    if q:
        qs = qs.filter(Q(title__icontains=q) | Q(excerpt__icontains=q) | Q(tags__icontains=q))
    page = Paginator(qs, 9).get_page(request.GET.get("page"))
    return render(request, "blog/index.html", {"page": page, "categories": Category.objects.filter(posts__published=True).distinct(),
                                               "current": cat, "q": q, "hide_nav": True, "canonical": request.build_absolute_uri("/blog/")})


def post(request, slug):
    p = get_object_or_404(Post.objects.select_related("category", "author"), slug=slug)
    if not p.published and not request.user.is_superuser:
        raise Http404
    if p.published:
        Post.objects.filter(pk=p.pk).update(views=F("views") + 1)
    related = Post.objects.filter(published=True).exclude(pk=p.pk)
    if p.category:
        related = related.filter(category=p.category)
    return render(request, "blog/post.html", {"p": p, "related": related[:3], "hide_nav": True,
                                              "canonical": p.canonical_url or request.build_absolute_uri(p.get_absolute_url())})


# â”€â”€ admin side â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€
@staff_required
def staff_list(request):
    from accounts.staff import paginate
    posts = Post.objects.select_related("category").order_by("-created")
    page = paginate(request, posts)
    return render(request, "staff/blog_list.html", {"posts": page, "page": page, "section": "blog", "hide_nav": True,
                                                    "published": posts.filter(published=True).count()})


@staff_required
def staff_edit(request, post_id=None):
    p = get_object_or_404(Post, pk=post_id) if post_id else None
    if request.method == "POST":
        data = request.POST
        if not p:
            p = Post(author=request.user)
        p.title = data.get("title", "").strip()[:160]
        p.slug = data.get("slug", "").strip()[:180]
        p.excerpt = data.get("excerpt", "").strip()[:300]
        p.body_html = data.get("body_html", "")
        p.featured_image = data.get("featured_image", "").strip()
        p.featured_image_alt = data.get("featured_image_alt", "").strip()[:160]
        p.tags = data.get("tags", "").strip()[:200]
        p.author_name = data.get("author_name", "").strip()[:80]
        p.seo_title = data.get("seo_title", "").strip()[:70]
        p.meta_description = data.get("meta_description", "").strip()[:160]
        p.canonical_url = data.get("canonical_url", "").strip()
        p.og_title = data.get("og_title", "").strip()[:95]
        p.og_description = data.get("og_description", "").strip()[:200]
        p.og_image = data.get("og_image", "").strip()
        cat_name = data.get("category", "").strip()[:60]
        p.category = Category.objects.get_or_create(name=cat_name)[0] if cat_name else None
        action = data.get("action", "save")
        if action == "publish":
            p.published = True
            if not p.published_at:
                p.published_at = timezone.now()
        elif action == "unpublish":
            p.published = False
        if data.get("published_at"):
            try:
                from django.utils.dateparse import parse_datetime
                dt = parse_datetime(data["published_at"])
                if dt:
                    p.published_at = timezone.make_aware(dt) if timezone.is_naive(dt) else dt
            except (ValueError, TypeError):
                pass
        if not p.title or not p.body_html.strip():
            messages.error(request, "A post needs a title and a body.")
        else:
            p.save()
            messages.success(request, f"Saved \"{p.title}\" ({'published' if p.published else 'draft'}).")
            return redirect("staff_blog_edit", post_id=p.pk)
    return render(request, "staff/blog_edit.html", {"p": p, "categories": Category.objects.all(), "section": "blog", "hide_nav": True})


@staff_required
@require_POST
def staff_delete(request, post_id):
    p = get_object_or_404(Post, pk=post_id)
    title = p.title
    p.delete()
    messages.warning(request, f"Deleted \"{title}\".")
    return redirect("staff_blog")
