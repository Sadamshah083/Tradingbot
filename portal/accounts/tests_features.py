"""Leads, admin chat console, customer chat pop-up and the blog (pictures, categories, hidden tags)."""
import shutil
import tempfile
from datetime import timedelta

from django.core.files.uploadedfile import SimpleUploadedFile
from django.test import TestCase, override_settings
from django.urls import reverse
from django.utils import timezone

from accounts.models import Profile
from accounts.tests_roles import PW, User, make, web_login
from blog.models import Category, Post
from chat.models import Message

PNG = b"\x89PNG\r\n\x1a\n" + b"\x00" * 64


class Leads(TestCase):
    def setUp(self):
        self.owner = make("owner", superuser=True)
        self.admin = make("adm", "admin")
        self.agent = make("agt", "agent")

    def test_signup_becomes_a_lead_with_a_welcome_message(self):
        r = self.client.post(reverse("register"), {"username": "newbie", "email": "newbie@example.com", "password1": "Str0ng-pass-99", "password2": "Str0ng-pass-99"})
        self.assertEqual(r.status_code, 302)
        u = User.objects.get(username="newbie")
        self.assertEqual(u.profile.lead_status, "new")
        self.assertTrue(Message.objects.filter(customer=u, auto=True, from_admin=True).exists())
        web_login(self.client, "adm")
        page = self.client.get(reverse("staff_leads")).content.decode()
        self.assertIn("newbie@example.com", page)

    def test_only_admins_see_leads(self):
        make("lead1")
        for name, code in (("owner", 200), ("adm", 200), ("agt", 403), ("lead1", 403)):
            web_login(self.client, name)
            self.assertEqual(self.client.get(reverse("staff_leads")).status_code, code, name)

    def test_status_and_note_update_and_paid_users_show_as_customers(self):
        from orders.models import Order
        lead = make("lead2")
        buyer = make("buyer")
        Order.objects.create(user=buyer, product="bot", amount_usd=20, status="paid", reference="x")
        web_login(self.client, "adm")
        self.client.post(reverse("staff_lead_update", args=[lead.id]), {"status": "contacted", "note": "called on Monday"})
        lead.profile.refresh_from_db()
        self.assertEqual((lead.profile.lead_status, lead.profile.lead_note), ("contacted", "called on Monday"))
        html = self.client.get(reverse("staff_leads")).content.decode()
        self.assertIn('class="stage customer"', html)      # the buyer stays on the list, marked as a customer


class ChatConsoleAndPopup(TestCase):
    def setUp(self):
        self.cust = make("cust")
        self.agent = make("agt", "agent")
        Message.objects.create(customer=self.cust, from_admin=False, author=self.cust, text="hello there")

    def test_console_list_and_old_url_redirect(self):
        web_login(self.client, "agt")
        d = self.client.get(reverse("chat_inbox_list")).json()
        self.assertEqual([r["username"] for r in d["rows"]], ["cust"])
        self.assertEqual(d["unread_total"], 1)
        r = self.client.get(reverse("chat_conversation", args=[self.cust.id]))
        self.assertEqual(r["Location"], f"{reverse('chat_inbox')}?u={self.cust.id}")
        self.assertEqual(self.client.get(reverse("chat_inbox")).status_code, 200)

    def test_popup_opens_once_after_login_for_customers_only(self):
        r = self.client.post(reverse("login"), {"username": "cust", "password": PW})
        self.assertEqual(r.status_code, 302)
        first = self.client.get(reverse("dashboard")).content.decode()
        self.assertIn('id="cp"', first)
        self.assertIn('data-open="1"', first)
        second = self.client.get(reverse("dashboard")).content.decode()
        self.assertNotIn('data-open="1"', second)
        web_login(self.client, "agt")
        self.assertNotIn('id="cp"', self.client.get(reverse("chat_inbox")).content.decode())


class BlogFeatures(TestCase):
    def setUp(self):
        self.tmp = tempfile.mkdtemp()
        self.override = override_settings(MEDIA_ROOT=self.tmp)
        self.override.enable()
        self.owner = make("owner", superuser=True)
        web_login(self.client, "owner")

    def tearDown(self):
        self.override.disable()
        shutil.rmtree(self.tmp, ignore_errors=True)

    def save_post(self, **extra):
        data = {"title": "Gold risk guide", "body_html": "<p>Body text</p>", "tags": "secret-internal-tag, gold", "action": "publish", "new_category": "Risk"}
        data.update(extra)
        return self.client.post(reverse("staff_blog_new"), data)

    def test_picture_upload_is_shown_and_tags_stay_internal(self):
        r = self.save_post(featured_file=SimpleUploadedFile("cover.png", PNG, content_type="image/png"))
        self.assertEqual(r.status_code, 302)
        p = Post.objects.get(title="Gold risk guide")
        self.assertTrue(p.featured_file.name.startswith("blog/"))
        self.client.logout()
        page = self.client.get(p.get_absolute_url()).content.decode()
        self.assertIn(p.featured_file.url, page)
        self.assertNotIn("secret-internal-tag", page)
        self.assertEqual(self.client.get(p.featured_file.url).status_code, 200)
        listing = self.client.get(reverse("blog")).content.decode()
        self.assertNotIn("secret-internal-tag", listing)

    def test_fake_picture_is_rejected(self):
        r = self.save_post(featured_file=SimpleUploadedFile("evil.png", b"<script>alert(1)</script>", content_type="image/png"))
        self.assertEqual(r.status_code, 200)               # form shown again with an error
        self.assertFalse(Post.objects.exists())
        r = self.save_post(featured_file=SimpleUploadedFile("evil.php", PNG, content_type="image/png"))
        self.assertFalse(Post.objects.exists())

    def test_category_pages_and_published_date_not_updated_date(self):
        self.save_post()
        p = Post.objects.get()
        Post.objects.filter(pk=p.pk).update(published_at=timezone.now() - timedelta(days=30), updated=timezone.now())
        self.client.logout()
        cat = Category.objects.get(name="Risk")
        html = self.client.get(reverse("blog_category", args=[cat.slug])).content.decode()
        self.assertIn("Gold risk guide", html)
        shown = timezone.localtime(timezone.now() - timedelta(days=30)).strftime("%b %d, %Y")   # templates render in the site time zone
        self.assertIn(shown, html)
        post_html = self.client.get(p.get_absolute_url()).content.decode()
        self.assertNotIn(timezone.now().strftime("%b %d, %Y"), html.replace(shown, "")) if shown != timezone.now().strftime("%b %d, %Y") else None
        self.assertIn('"dateModified":"' + timezone.localtime(timezone.now() - timedelta(days=30)).strftime("%Y-%m-%d"), post_html)
