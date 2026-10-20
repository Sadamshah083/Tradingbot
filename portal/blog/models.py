from django.conf import settings
from django.db import models
from django.urls import reverse
from django.utils import timezone
from django.utils.text import slugify


class Category(models.Model):
    name = models.CharField(max_length=60, unique=True)
    slug = models.SlugField(max_length=70, unique=True, blank=True)

    class Meta:
        ordering = ["name"]
        verbose_name_plural = "categories"

    def save(self, *args, **kwargs):
        if not self.slug:
            self.slug = slugify(self.name)[:70]
        super().save(*args, **kwargs)

    def __str__(self):
        return self.name


class Post(models.Model):
    """A blog article written in HTML by the admin."""
    title = models.CharField(max_length=160)
    slug = models.SlugField(max_length=180, unique=True, blank=True)
    excerpt = models.CharField(max_length=300, blank=True, help_text="Short summary for the listing and social cards.")
    body_html = models.TextField(help_text="Article body in HTML.")
    featured_image = models.URLField(blank=True, help_text="Full URL of the cover image (upload it anywhere public, e.g. Imgur, or /static/).")
    featured_image_alt = models.CharField(max_length=160, blank=True)
    category = models.ForeignKey(Category, null=True, blank=True, on_delete=models.SET_NULL, related_name="posts")
    tags = models.CharField(max_length=200, blank=True, help_text="Comma-separated.")
    author = models.ForeignKey(settings.AUTH_USER_MODEL, null=True, blank=True, on_delete=models.SET_NULL, related_name="posts")
    author_name = models.CharField(max_length=80, blank=True, help_text="Shown publicly; defaults to the site name.")
    # SEO
    seo_title = models.CharField(max_length=70, blank=True)
    meta_description = models.CharField(max_length=160, blank=True)
    canonical_url = models.URLField(blank=True)
    og_title = models.CharField(max_length=95, blank=True)
    og_description = models.CharField(max_length=200, blank=True)
    og_image = models.URLField(blank=True)
    published = models.BooleanField(default=False)
    published_at = models.DateTimeField(null=True, blank=True)
    created = models.DateTimeField(auto_now_add=True)
    updated = models.DateTimeField(auto_now=True)
    views = models.PositiveIntegerField(default=0)

    class Meta:
        ordering = ["-published_at", "-created"]

    def __str__(self):
        return self.title

    def save(self, *args, **kwargs):
        if not self.slug:
            base = slugify(self.title)[:170] or "post"
            slug, n = base, 2
            while Post.objects.filter(slug=slug).exclude(pk=self.pk).exists():
                slug = f"{base}-{n}"; n += 1
            self.slug = slug
        if self.published and not self.published_at:
            self.published_at = timezone.now()
        super().save(*args, **kwargs)

    def get_absolute_url(self):
        return reverse("blog_post", args=[self.slug])

    @property
    def tag_list(self):
        return [t.strip() for t in self.tags.split(",") if t.strip()]

    @property
    def reading_minutes(self):
        import re
        words = len(re.sub(r"<[^>]+>", " ", self.body_html).split())
        return max(1, round(words / 220))
