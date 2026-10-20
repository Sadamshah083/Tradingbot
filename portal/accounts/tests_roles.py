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
        for u, code in ((self.owner, 200), (self.admin, 200), (self.agent, 302), (self.cust, 302)):
            self.login(u)
            self.assertEqual(self.client.get(reverse("staff_customers")).status_code, code, u.username)

    def test_chat_inbox(self):
        for u, code in ((self.owner, 200), (self.admin, 200), (self.agent, 200), (self.cust, 302)):
            self.login(u)
            self.assertEqual(self.client.get(reverse("chat_inbox")).status_code, code, u.username)

    def test_bot_control_is_superadmin_only(self):
        self.login(self.admin)
        self.assertEqual(self.client.post(reverse("staff_bot_mode"), {"auto": "1"}).status_code, 302)
        self.assertIn("admin/login", self.client.post(reverse("staff_bot_mode"), {"auto": "1"})["Location"])

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
        for u, target in ((self.cust, "/accounts/dashboard/"), (self.agent, "/chat/inbox/"), (self.admin, "/accounts/staff/"), (self.owner, "/accounts/staff/")):
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
        self.assertEqual(self.client.get(reverse("chat_staff_poll", args=[other.id])).status_code, 302)


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
