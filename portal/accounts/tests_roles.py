"""Roles, chat and the single-superadmin rule."""
from django.contrib.auth import get_user_model
from django.core.management import call_command
from django.test import TestCase, override_settings
from django.urls import reverse

from accounts.models import Profile
from chat.models import Message

User = get_user_model()
PW = "Test-pass-12345"


def web_login(client, username):
    """Log in through the real login view so the JWT cookie is issued (a bare session is rejected by the middleware)."""
    client.logout()
    r = client.post(reverse("login"), {"username": username, "password": PW})
    assert r.status_code == 302, r.status_code


def make(username, role="customer", superuser=False, email=None):
    u = User.objects.create_user(username=username, email=email or f"{username}@example.com", password=PW)
    if superuser:
        u.is_superuser = u.is_staff = True
        u.save()
    p, _ = Profile.objects.get_or_create(user=u)
    p.role = role
    p.save()
    return u


class RoleAccess(TestCase):
    def setUp(self):
        self.owner = make("owner", superuser=True, email="owner@example.com")
        self.admin = make("adm", "admin")
        self.agent = make("agt", "agent")
        self.cust = make("cust")

    def login(self, u):
        web_login(self.client, u.username)

    def test_customers_page(self):
        for u, code in ((self.owner, 200), (self.admin, 200), (self.agent, 403), (self.cust, 403)):
            self.login(u)
            self.assertEqual(self.client.get(reverse("staff_leads")).status_code, code, u.username)

    def test_chat_inbox(self):
        for u, code in ((self.owner, 200), (self.admin, 200), (self.agent, 200), (self.cust, 403)):
            self.login(u)
            self.assertEqual(self.client.get(reverse("chat_inbox")).status_code, code, u.username)

    def test_bot_control_is_superadmin_only(self):
        self.login(self.admin)
        self.assertEqual(self.client.post(reverse("staff_bot_mode"), {"auto": "1"}).status_code, 403)

    def test_only_superadmin_assigns_roles(self):
        self.login(self.admin)
        self.client.post(reverse("staff_customer_update", args=[self.cust.id]), {"action": "set_role", "role": "admin"})
        self.cust.profile.refresh_from_db()
        self.assertEqual(self.cust.profile.role, "customer")
        self.login(self.owner)
        self.client.post(reverse("staff_customer_update", args=[self.cust.id]), {"action": "set_role", "role": "agent"})
        self.cust.profile.refresh_from_db()
        self.assertEqual(self.cust.profile.role, "agent")

    def test_admin_cannot_delete_customer(self):
        self.login(self.admin)
        self.client.post(reverse("staff_customer_update", args=[self.cust.id]), {"action": "delete"})
        self.assertTrue(User.objects.filter(pk=self.cust.pk).exists())

    def test_login_lands_by_role(self):
        for u, target in ((self.cust, "/accounts/dashboard/"), (self.agent, "/chat/inbox/"), (self.admin, "/admin/Dashboard"), (self.owner, "/admin/Dashboard")):
            self.client.logout()
            r = self.client.post(reverse("login"), {"username": u.username, "password": PW})
            self.assertEqual(r.status_code, 302, u.username)
            self.assertEqual(r["Location"], target, u.username)

    def test_customer_cannot_use_team_login(self):
        r = self.client.post(reverse("admin_login"), {"username": "cust", "password": PW})
        self.assertEqual(r.status_code, 200)   # form re-rendered with an error


class ChatFlow(TestCase):
    def setUp(self):
        self.cust = make("cust")
        self.agent = make("agt", "agent")

    def test_auto_ack_once_and_not_after_a_human_reply(self):
        web_login(self.client, "cust")
        self.client.post(reverse("chat_send"), {"text": "hello"})
        self.client.post(reverse("chat_send"), {"text": "anyone there?"})
        self.assertEqual(Message.objects.filter(customer=self.cust, auto=True).count(), 1)
        self.assertEqual(Message.objects.filter(customer=self.cust, from_admin=False).count(), 2)

    def test_no_auto_when_agent_replied_recently(self):
        Message.objects.create(customer=self.cust, from_admin=True, author=self.agent, text="hi")
        web_login(self.client, "cust")
        self.client.post(reverse("chat_send"), {"text": "thanks"})
        self.assertFalse(Message.objects.filter(auto=True).exists())

    def test_agent_presence_and_reply(self):
        web_login(self.client, "agt")
        self.client.get(reverse("chat_inbox"))
        r = self.client.post(reverse("chat_staff_send", args=[self.cust.id]), {"text": "hello customer"})
        self.assertEqual(r.status_code, 200)
        web_login(self.client, "cust")
        d = self.client.get(reverse("chat_poll")).json()
        self.assertTrue(d["agents_online"])
        self.assertEqual([m["text"] for m in d["items"]], ["hello customer"])

    def test_customers_cannot_read_each_other(self):
        other = make("other")
        Message.objects.create(customer=other, from_admin=False, author=other, text="secret")
        web_login(self.client, "cust")
        self.assertEqual(self.client.get(reverse("chat_poll")).json()["items"], [])
        self.assertEqual(self.client.get(reverse("chat_staff_poll", args=[other.id])).status_code, 403)


@override_settings(SUPERADMIN_EMAIL="boss@example.com")
class SingleSuperadmin(TestCase):
    def test_only_one_superuser_remains_and_roles_survive(self):
        boss = make("boss", superuser=True, email="boss@example.com")
        extra = make("extra", superuser=True, email="extra@example.com")
        agent = make("agt", "agent")
        call_command("ensure_superadmin")
        boss.refresh_from_db(); extra.refresh_from_db(); agent.profile.refresh_from_db()
        self.assertTrue(boss.is_superuser)
        self.assertFalse(extra.is_superuser or extra.is_staff)
        self.assertEqual(agent.profile.role, "agent")
        self.assertEqual(User.objects.filter(is_superuser=True).count(), 1)


class StaffRouting(TestCase):
    def setUp(self):
        self.owner = make("owner", superuser=True)
        self.admin = make("adm", "admin")
        self.agent = make("agt", "agent")
        self.cust = make("cust")

    def test_canonical_dashboard_and_old_urls(self):
        self.assertEqual(reverse("staff_home"), "/admin/Dashboard")
        web_login(self.client, "owner")
        self.assertEqual(self.client.get("/admin/Dashboard").status_code, 200)
        for old in ("/accounts/staff/", "/admin/", "/admin/dashboard", "/admin/Dashboard/"):
            r = self.client.get(old)
            self.assertEqual((r.status_code, r["Location"]), (302, "/admin/Dashboard"), old)     # one hop, no loop

    def test_agent_is_sent_to_the_inbox_not_the_dashboard(self):
        web_login(self.client, "agt")
        r = self.client.get("/accounts/staff/")
        self.assertEqual(r["Location"], reverse("chat_inbox"))
        self.assertEqual(self.client.get("/admin/Dashboard").status_code, 403)

    def test_anonymous_goes_to_login_and_returns_afterwards(self):
        r = self.client.get("/admin/Dashboard")
        self.assertEqual(r.status_code, 302)
        self.assertEqual(r["Location"], "/admin/login/?next=/admin/Dashboard")
        r = self.client.get("/accounts/staff/customers/")
        self.assertEqual(r["Location"], "/admin/login/?next=/accounts/staff/customers/")
        r = self.client.post("/admin/login/?next=/accounts/staff/customers/", {"username": "owner", "password": PW})
        self.assertEqual((r.status_code, r["Location"]), (302, "/accounts/staff/customers/"))
        r = self.client.get("/accounts/staff/")             # already signed in: forwarded in one hop
        self.assertEqual(r["Location"], "/admin/Dashboard")

    def test_unsafe_next_is_ignored(self):
        r = self.client.post("/admin/login/?next=https://evil.example/", {"username": "owner", "password": PW})
        self.assertEqual(r["Location"], "/admin/Dashboard")

    def test_customers_never_reach_admin_pages(self):
        web_login(self.client, "cust")
        for url in ("/admin/Dashboard", "/accounts/staff/", "/accounts/staff/leads/", "/admin/Settings", "/bot/staff/connections/",
                    "/orders/staff/", "/blog/staff/", "/chat/inbox/"):
            self.assertEqual(self.client.get(url).status_code, 403, url)

    def test_every_sidebar_link_resolves_for_the_superadmin(self):
        import re
        web_login(self.client, "owner")
        html = self.client.get("/admin/Dashboard").content.decode()
        hrefs = set(re.findall(r'class="item[^"]*" href="([^"]+)"', html))
        self.assertGreaterEqual(len(hrefs), 10)
        for h in hrefs:
            if h.startswith("/") and h != "/":
                code = self.client.get(h).status_code
                self.assertIn(code, (200, 302), f"{h} -> {code}")
