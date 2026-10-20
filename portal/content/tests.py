"""Home page cards/reviews, contact form, blog redirects, noindex and the unchanged hero."""
import subprocess
from pathlib import Path
from unittest import mock

from django.core import mail
from django.test import TestCase, override_settings
from django.urls import reverse

from accounts.tests_roles import make, web_login
from blog.models import Post, SlugRedirect
from content.models import ContactMessage, Review
from orders.models import Order

LANDING = Path(__file__).resolve().parent.parent / "templates" / "landing.html"
MAIL = dict(EMAIL_HOST="smtp.example.test", SUPPORT_EMAIL="support@sambot.test", DEFAULT_FROM_EMAIL="noreply@sambot.test")


def hero_block(text: str) -> str:
    text = text.replace("\r\n", "\n")
    a = text.index('<div class="hero-band">')
    return text[a:text.index('<div class="statbar"', a)]


class HomeAndHero(TestCase):
    def test_hero_markup_is_identical_to_the_last_commit(self):
        head = subprocess.run(["git", "show", "HEAD:portal/templates/landing.html"], cwd=LANDING.parent.parent.parent, capture_output=True, text=True, encoding="utf-8")
        if head.returncode != 0:
            self.skipTest("git history not available")
        self.assertEqual(hero_block(head.stdout), hero_block(LANDING.read_text(encoding="utf-8")))

    def test_card_section_links_to_real_pages_and_search_is_gone(self):
        html = self.client.get("/").content.decode()
        self.assertEqual(html.count('class="hc"'), 6)
        cards = html[html.index('id="features"'):]
        for name in ("site_tradingview", "site_markets", "site_paper", "site_risk", "site_mt5", "site_how"):
            self.assertIn(f'href="{reverse(name)}"', cards)
        self.assertEqual(html.count("<h1"), 1)
        self.assertNotIn("Search articles", self.client.get(reverse("blog")).content.decode())
        nav = html[html.index('<ul class="links">'):html.index("</ul>", html.index('<ul class="links">'))]
        self.assertNotIn("Search", nav)

    def test_reviews_section_hidden_until_real_approved_reviews_exist(self):
        u = make("rev1")
        self.assertNotIn('id="reviews"', self.client.get("/").content.decode())
        r = Review.objects.create(user=u, display_name="Sam K.", rating=5, text="<b>Clear paper mode</b> and risk limits, easy to follow.", consent=True)
        self.assertNotIn('id="reviews"', self.client.get("/").content.decode())
        r.status = "approved"
        r.save()
        html = self.client.get("/").content.decode()
        self.assertIn('id="reviews"', html)
        self.assertIn("&lt;b&gt;Clear paper mode", html)
        self.assertNotIn("rev1@example.com", html)
        self.assertNotIn("Verified customer</span>", html)
        Order.objects.create(user=u, product="bot", amount_usd=20, status="paid", reference="x")
        self.assertIn("Verified customer</span>", self.client.get("/").content.decode())
        self.assertNotIn("AggregateRating", html)


class ReviewFlow(TestCase):
    def test_submission_rules_and_moderation(self):
        make("rev2")
        self.assertEqual(self.client.get(reverse("review_new")).status_code, 302)
        web_login(self.client, "rev2")
        bad = self.client.post(reverse("review_new"), {"display_name": "a@b.com", "rating": "9", "text": "short", "consent": ""})
        self.assertEqual(bad.status_code, 200)
        self.assertFalse(Review.objects.exists())
        ok = {"display_name": "Riley", "rating": "4", "text": "Setup took an evening and the activity log is clear.", "consent": "on"}
        self.assertEqual(self.client.post(reverse("review_new"), ok).status_code, 302)
        self.assertEqual(Review.objects.get().status, "pending")
        self.client.post(reverse("review_new"), {**ok, "display_name": "Riley2"})
        self.assertEqual(Review.objects.count(), 1)
        make("owner", superuser=True)
        web_login(self.client, "rev2")
        self.assertEqual(self.client.get(reverse("staff_reviews")).status_code, 403)
        web_login(self.client, "owner")
        self.assertIn("Riley", self.client.get(reverse("staff_reviews")).content.decode())
        self.client.post(reverse("staff_review_action", args=[Review.objects.get().id]), {"action": "approve"})
        self.assertEqual(Review.objects.get().status, "approved")


class ContactForm(TestCase):
    def post(self, ip="10.0.0.1", **over):
        data = {"name": "Alex", "email": "alex@example.com", "subject": "Webhook", "message": "How do I connect my alert to SamBot?"}
        data.update(over)
        return self.client.post(reverse("site_contact"), data, REMOTE_ADDR=ip)

    def test_validation_errors_are_inline_and_nothing_is_saved(self):
        html = self.post(email="nope", message="hi").content.decode()
        self.assertIn("valid e-mail", html)
        self.assertIn("at least 10 characters", html)
        self.assertIn('aria-invalid="true"', html)
        self.assertEqual(ContactMessage.objects.count(), 0)
        self.assertNotIn("your message was received", html)

    def test_saved_first_and_unconfigured_email_is_reported_honestly(self):
        html = self.post().content.decode()
        self.assertIn("your message was received", html)
        self.assertEqual(ContactMessage.objects.get().email_status, "not_configured")
        self.assertEqual(len(mail.outbox), 0)

    @override_settings(EMAIL_BACKEND="django.core.mail.backends.locmem.EmailBackend", **MAIL)
    def test_notification_uses_verified_sender_and_reply_to(self):
        self.post(email="visitor@example.com")
        self.assertEqual(ContactMessage.objects.get().email_status, "sent")
        msg = mail.outbox[0]
        self.assertEqual((msg.from_email, msg.reply_to, msg.to), ("noreply@sambot.test", ["visitor@example.com"], ["support@sambot.test"]))

    @override_settings(**MAIL)
    def test_email_failure_is_recorded_but_the_message_is_kept(self):
        with mock.patch("django.core.mail.message.EmailMessage.send", side_effect=OSError("smtp down")):
            html = self.post().content.decode()
        self.assertIn("your message was received", html)
        m = ContactMessage.objects.get()
        self.assertEqual((m.email_status, m.email_error), ("failed", "smtp down"))

    def test_rate_limit_and_honeypot(self):
        for i in range(3):
            self.post(message=f"Message number {i} for rate limiting")
        html = self.post(message="Message number four for rate limiting").content.decode()
        self.assertIn("several messages recently", html)
        self.assertEqual(ContactMessage.objects.count(), 3)
        self.client.post(reverse("site_contact"), {"email": "bot@example.com", "message": "buy cheap stuff now please", "website": "http://spam"}, REMOTE_ADDR="10.0.0.9")
        self.assertEqual(ContactMessage.objects.count(), 3)

    def test_staff_see_messages_with_delivery_status(self):
        self.post()
        make("owner", superuser=True)
        web_login(self.client, "owner")
        html = self.client.get(reverse("staff_messages")).content.decode()
        self.assertIn("alex@example.com", html)
        self.assertIn("not configured", html)


class BlogRedirectsAndIndexing(TestCase):
    def test_old_slug_redirects_permanently_and_drafts_stay_private(self):
        make("owner", superuser=True)
        web_login(self.client, "owner")
        body = {"title": "Paper trading before live", "body_html": "<p>x</p>", "action": "publish"}
        self.client.post(reverse("staff_blog_new"), {**body, "slug": "old-name"})
        p = Post.objects.get()
        self.client.post(reverse("staff_blog_edit", args=[p.id]), {**body, "slug": "paper-trading-before-live"})
        self.client.logout()
        r = self.client.get("/blog/old-name/")
        self.assertEqual((r.status_code, r["Location"]), (301, "/blog/paper-trading-before-live/"))
        self.assertEqual(self.client.get("/blog/paper-trading-before-live/").status_code, 200)
        draft = Post.objects.create(title="Draft idea", body_html="<p>d</p>", published=False)
        self.assertEqual(self.client.get(draft.get_absolute_url()).status_code, 404)
        sitemap = self.client.get("/sitemap.xml").content.decode()
        self.assertIn("/blog/paper-trading-before-live/", sitemap)
        self.assertNotIn(draft.slug, sitemap)

    @override_settings(SITE_URL="https://example.org")
    def test_non_canonical_hosts_are_kept_out_of_search(self):
        r = self.client.get("/", HTTP_HOST="preview.example.net")
        self.assertEqual(r["X-Robots-Tag"], "noindex, nofollow")
        self.assertIn("Disallow: /\n", self.client.get("/robots.txt", HTTP_HOST="preview.example.net").content.decode())
        r = self.client.get("/", HTTP_HOST="example.org")
        self.assertNotIn("X-Robots-Tag", r)
        self.assertIn("Sitemap: https://example.org/sitemap.xml", self.client.get("/robots.txt", HTTP_HOST="example.org").content.decode())


class AiCrawlersAndLlms(TestCase):
    @override_settings(SITE_URL="https://example.org")
    def test_robots_names_ai_crawlers_keeps_private_areas_closed_and_lists_sitemap(self):
        txt = self.client.get("/robots.txt", HTTP_HOST="example.org").content.decode()
        for bot in ("GPTBot", "ClaudeBot", "PerplexityBot", "Google-Extended", "CCBot", "Bingbot", "OAI-SearchBot"):
            self.assertIn(f"User-agent: {bot}", txt)
        self.assertIn("Disallow: /accounts/", txt)
        self.assertIn("Disallow: /chat/", txt)
        self.assertIn("Sitemap: https://example.org/sitemap.xml", txt)
        self.assertIn("llms.txt", txt)

    def test_llms_files_summarise_the_public_site_without_private_urls(self):
        short = self.client.get("/llms.txt")
        self.assertEqual(short.status_code, 200)
        body = short.content.decode()
        self.assertTrue(body.startswith("# "))
        self.assertIn("> ", body)
        self.assertIn("/how/", body)
        self.assertNotIn("/accounts/", body)
        full = self.client.get("/llms-full.txt").content.decode()
        self.assertIn("## Pricing", full)
        self.assertIn("does not guarantee", full)
        self.assertNotIn("/admin/", full)
