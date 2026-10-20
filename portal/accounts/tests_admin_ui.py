"""Admin sidebar (no Customers / no Django admin), Leads with all customer actions, Settings (team), paid-delivery tables."""
from django.urls import reverse

from django.test import TestCase

from accounts.models import Profile
from accounts.tests_roles import PW, User, make, web_login
from signals.models import Signal, SignalDelivery


class AdminSidebarAndLeads(TestCase):
    def setUp(self):
        self.owner = make("owner", superuser=True)
        self.admin = make("adm", "admin")
        self.lead = make("lead1", email="lead1@example.com")

    def test_sidebar_has_no_customers_or_django_admin(self):
        web_login(self.client, "owner")
        html = self.client.get(reverse("staff_home")).content.decode()
        side = html[html.index('<aside class="side"'):html.index("</aside>")]
        self.assertNotIn(">Customers<", side.replace("</svg>", "><"))
        self.assertNotIn("Django admin", side)
        for label in ("Leads", "Settings", "Live chat", "Signals", "Manual trader"):
            self.assertIn(label, side)
        self.assertEqual(self.client.get("/django-admin/").status_code, 404)

    def test_old_customers_url_forwards_to_leads_keeping_the_search(self):
        web_login(self.client, "owner")
        r = self.client.get("/accounts/staff/customers/?q=lead1")
        self.assertEqual((r.status_code, r["Location"]), (302, reverse("staff_leads") + "?q=lead1"))

    def test_leads_rows_have_a_three_dot_menu(self):
        web_login(self.client, "owner")
        html = self.client.get(reverse("staff_leads")).content.decode()
        self.assertIn('class="dots"', html)
        for label in ("Open chat", "Add signal credits", "Grant bot access", "Pause account", "Edit details", "Edit e-mail &amp; password", "Delete account"):
            self.assertIn(f"<span>{label}", html, label)
        web_login(self.client, "adm")
        admin_html = self.client.get(reverse("staff_leads")).content.decode()
        self.assertNotIn("<span>Delete account", admin_html)       # destructive action stays superadmin-only
        self.assertIn("<span>Add signal credits", admin_html)

    def test_customer_actions_work_from_leads(self):
        web_login(self.client, "adm")
        self.client.post(reverse("staff_customer_update", args=[self.lead.id]), {"action": "add_credits", "credits": "5", "reason": "x", "next": reverse("staff_leads")})
        self.lead.profile.refresh_from_db()
        self.assertEqual(self.lead.profile.credits, 5)
        self.client.post(reverse("staff_customer_update", args=[self.lead.id]), {"action": "toggle"})
        self.lead.profile.refresh_from_db()
        self.assertFalse(self.lead.profile.active)

    def test_team_members_do_not_appear_as_leads(self):
        web_login(self.client, "owner")
        html = self.client.get(reverse("staff_leads")).content.decode()
        self.assertIn("lead1@example.com", html)
        self.assertNotIn("adm@example.com", html)


class SettingsTeam(TestCase):
    def setUp(self):
        self.owner = make("owner", superuser=True, email="owner@example.com")
        self.admin = make("adm", "admin", email="adm@example.com")
        self.agent = make("agt", "agent", email="agt@example.com")
        self.cust = make("cust")

    def test_only_the_superadmin_can_open_settings(self):
        for name, code in (("owner", 200), ("adm", 403), ("agt", 403), ("cust", 403)):
            web_login(self.client, name)
            self.assertEqual(self.client.get(reverse("staff_settings")).status_code, code, name)

    def test_page_lists_the_team_but_never_a_password_or_hash(self):
        web_login(self.client, "owner")
        html = self.client.get(reverse("staff_settings")).content.decode()
        for who in ("owner@example.com", "adm@example.com", "agt@example.com"):
            self.assertIn(who, html)
        self.assertNotIn("cust@example.com", html)
        self.assertNotIn("pbkdf2_", html)
        self.assertNotIn(PW, html)
        self.assertIn("••••••••••", html)      # password column is masked
        self.assertIn('id="popReset"', html)
        self.assertIn('id="popAdd"', html)

    def test_reset_password_shows_the_new_one_exactly_once(self):
        web_login(self.client, "owner")
        self.client.post(reverse("staff_team_action"), {"action": "reset_password", "user_id": self.agent.id, "password": "Brand-new-pass-77"})
        first = self.client.get(reverse("staff_settings")).content.decode()
        self.assertIn("Brand-new-pass-77", first)
        self.assertNotIn("Brand-new-pass-77", self.client.get(reverse("staff_settings")).content.decode())
        self.agent.refresh_from_db()
        self.assertTrue(self.agent.check_password("Brand-new-pass-77"))
        self.client.post(reverse("staff_team_action"), {"action": "reset_password", "user_id": self.agent.id, "password": "short"})
        self.agent.refresh_from_db()
        self.assertTrue(self.agent.check_password("Brand-new-pass-77"))     # too short: unchanged

    def test_add_member_creates_an_account_with_a_generated_password(self):
        web_login(self.client, "owner")
        self.client.post(reverse("staff_team_action"), {"action": "add_member", "email": "new@example.com", "role": "agent"})
        u = User.objects.get(email="new@example.com")
        self.assertEqual(u.profile.role, "agent")
        self.assertTrue(u.has_usable_password())
        html = self.client.get(reverse("staff_settings")).content.decode()
        self.assertIn("New password set", html)
        self.assertIn("new@example.com", html)

    def test_admins_cannot_use_the_team_actions_and_superadmin_is_protected(self):
        web_login(self.client, "adm")
        self.assertEqual(self.client.post(reverse("staff_team_action"), {"action": "set_role", "user_id": self.cust.id, "role": "admin"}).status_code, 403)
        web_login(self.client, "owner")
        self.client.post(reverse("staff_team_action"), {"action": "set_role", "user_id": self.owner.id, "role": "agent"})
        self.client.post(reverse("staff_team_action"), {"action": "toggle_active", "user_id": self.owner.id})
        self.owner.refresh_from_db()
        self.assertTrue(self.owner.is_superuser and self.owner.is_active)


class PaidDeliveryTables(TestCase):
    def setUp(self):
        self.owner = make("owner", superuser=True)
        buyer = make("buyer", email="buyer@example.com")
        for i in range(20):
            sig = Signal.objects.create(event="signal", side="buy", symbol="XAUUSD", timeframe="60", external_id=f"p{i}", source="admin" if i % 2 else "bot")
            SignalDelivery.objects.create(signal=sig, user=buyer, charged=True, credits_after=100 - i)
        free = Signal.objects.create(event="exit", side="buy", symbol="XAUUSD", timeframe="60", external_id="free")
        SignalDelivery.objects.create(signal=free, user=buyer, charged=False)
        web_login(self.client, "owner")

    def test_manual_trader_and_signals_pages_list_paid_deliveries_with_pagination(self):
        for name in ("staff_manual", "staff_signals"):
            html = self.client.get(reverse(name)).content.decode()
            self.assertIn("Paid signal deliveries", html)
            self.assertIn("20 total", html)                     # the free exit notice is not counted
            self.assertEqual(html.count("buyer@example.com"), 15)
            self.assertIn("dpage=2", html)
            page2 = self.client.get(reverse(name) + "?dpage=2").content.decode()
            self.assertEqual(page2.count("buyer@example.com"), 5)

    def test_empty_state_before_anyone_pays(self):
        SignalDelivery.objects.all().delete()
        html = self.client.get(reverse("staff_manual")).content.decode()
        self.assertIn("No customer has paid for a signal yet", html)


class ProfileSettings(TestCase):
    def setUp(self):
        self.u = make("pat", email="pat@example.com")

    def test_settings_page_and_navbar_menu(self):
        web_login(self.client, "pat")
        html = self.client.get(reverse("account_settings")).content.decode()
        self.assertIn("Change password", html)
        self.assertIn('id="umBtn"', html)
        self.assertIn(reverse("account_settings"), html)
        self.assertIn('id="umBtn"', self.client.get("/").content.decode())     # public site navbar too
        self.client.logout()
        self.assertEqual(self.client.get(reverse("account_settings")).status_code, 302)

    def test_picture_upload_name_and_validation(self):
        import shutil, tempfile
        from django.core.files.uploadedfile import SimpleUploadedFile
        from django.test import override_settings
        tmp = tempfile.mkdtemp()
        with override_settings(MEDIA_ROOT=tmp):
            web_login(self.client, "pat")
            png = b"\x89PNG\r\n\x1a\n" + b"\x00" * 64
            self.client.post(reverse("account_settings"), {"action": "profile", "first_name": "Pat", "email": "pat@example.com", "avatar": SimpleUploadedFile("a.png", png, content_type="image/png")})
            self.u.refresh_from_db(); self.u.profile.refresh_from_db()
            self.assertEqual(self.u.first_name, "Pat")
            self.assertTrue(self.u.profile.avatar.name.startswith("avatars/"))
            self.assertIn(self.u.profile.avatar.url, self.client.get(reverse("dashboard")).content.decode())
            self.client.post(reverse("account_settings"), {"action": "profile", "first_name": "Pat", "email": "pat@example.com", "avatar": SimpleUploadedFile("evil.png", b"<script>", content_type="image/png")})
            self.u.profile.refresh_from_db()
            self.assertTrue(self.u.profile.avatar)                      # fake picture rejected, old one kept
        shutil.rmtree(tmp, ignore_errors=True)

    def test_email_must_be_unique_and_password_change_checks_old_password(self):
        make("other", email="other@example.com")
        web_login(self.client, "pat")
        self.client.post(reverse("account_settings"), {"action": "profile", "first_name": "", "email": "other@example.com"})
        self.u.refresh_from_db()
        self.assertEqual(self.u.email, "pat@example.com")
        self.client.post(reverse("account_settings"), {"action": "password", "old_password": "wrong", "new_password1": "Another-pass-4321", "new_password2": "Another-pass-4321"})
        self.u.refresh_from_db()
        self.assertTrue(self.u.check_password(PW))
        self.client.post(reverse("account_settings"), {"action": "password", "old_password": PW, "new_password1": "Another-pass-4321", "new_password2": "Another-pass-4321"})
        self.u.refresh_from_db()
        self.assertTrue(self.u.check_password("Another-pass-4321"))
        self.assertEqual(self.client.get(reverse("dashboard")).status_code, 200)   # still signed in

    def test_admin_can_set_a_customer_password_and_leads_has_no_private_note(self):
        make("owner", superuser=True)
        web_login(self.client, "owner")
        html = self.client.get(reverse("staff_leads")).content.decode()
        self.assertNotIn("Private note", html)
        self.assertNotIn("Follow-up", html)
        self.assertNotIn("Interested", html)
        self.assertIn("<th>Password</th>", html)
        self.client.post(reverse("staff_customer_update", args=[self.u.id]), {"action": "set_password", "password": "Set-by-admin-123"})
        self.u.refresh_from_db()
        self.assertTrue(self.u.check_password("Set-by-admin-123"))


class EditAccountPopup(TestCase):
    def test_email_and_password_in_one_action(self):
        make("owner", superuser=True)
        cust = make("c1", email="c1@example.com")
        make("c2", email="c2@example.com")
        web_login(self.client, "owner")
        url = reverse("staff_customer_update", args=[cust.id])
        self.client.post(url, {"action": "account", "email": "new1@example.com", "password": "Fresh-pass-5555"})
        cust.refresh_from_db()
        self.assertEqual(cust.email, "new1@example.com")
        self.assertTrue(cust.check_password("Fresh-pass-5555"))
        self.client.post(url, {"action": "account", "email": "c2@example.com", "password": ""})      # taken by someone else
        cust.refresh_from_db()
        self.assertEqual(cust.email, "new1@example.com")
        self.client.post(url, {"action": "account", "email": "new1@example.com", "password": "short"})
        cust.refresh_from_db()
        self.assertTrue(cust.check_password("Fresh-pass-5555"))
        self.client.post(url, {"action": "account", "email": "new2@example.com", "password": ""})    # e-mail only keeps the password
        cust.refresh_from_db()
        self.assertEqual(cust.email, "new2@example.com")
        self.assertTrue(cust.check_password("Fresh-pass-5555"))
