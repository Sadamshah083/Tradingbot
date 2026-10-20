from django.contrib import admin

from .models import Category, Post


@admin.register(Post)
class PostAdmin(admin.ModelAdmin):
    list_display = ("title", "category", "published", "published_at", "views")
    list_filter = ("published", "category")
    search_fields = ("title", "body_html", "tags")
    prepopulated_fields = {"slug": ("title",)}


admin.site.register(Category)
