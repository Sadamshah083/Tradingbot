"""Paid-signal delivery, entitlement, auditing, and verified MT5 connection status."""
import json
from datetime import timedelta

from django.test import TestCase, override_settings
from django.urls import reverse
from django.utils import timezone

from accounts.tests_roles import PW, User, make, web_login
from bots.models import BotSettings, BrokerConnection, Execution
from orders.models import Order
from signals.models import Signal, SignalDelivery
from signals.services import deliver, signal_status

SECRET = "hook-secret"
TOKEN = "bridge-token-very-secret"


def ingest(client, **over):
    p = {"event": "signal", "side": "buy", "symbol": "XAUUSD", "tf": "60", "price": 2400.5, "sl": 2390, "tp2": 2420, "id": over.pop("id", "t1")}
    p.update(over)
    return client.post(reverse("api_ingest"), data=json.dumps(p), content_type="application/json", HTTP_X_WEBHOOK_SECRET=SECRET)


def give(user, credits):
    from accounts.models import Profile
    Profile.objects.filter(user=user).update(credits=credits)


@override_settings(WEBHOOK_SECRET=SECRET)
class SignalDeliveryRules(TestCase):
    def setUp(self):
        self.paid = make("paid")
        self.unpaid = make("unpaid")
        give(self.paid, 3)

    def test_table_starts_empty_even_when_signals_exist(self):
        ingest(self.client)
        web_login(self.client, "unpaid")
        html = self.client.get(reverse("dashboard")).content.decode()
        self.assertIn("No signals received yet.", html)
        self.assertNotIn("XAUUSD", html)                      # nothing protected in the page source
        self.assertEqual(self.client.get(reverse("signal_feed")).json()["items"], [])

    def test_only_entitled_user_receives_and_pays_once(self):
        r = ingest(self.client).json()
        self.assertEqual(r["delivered"], 1)
        self.assertEqual(SignalDelivery.objects.count(), 1)
        self.paid.profile.refresh_from_db()
        self.assertEqual(self.paid.profile.credits, 2)
        # duplicate alert (same external id) and a repeated deliver() call must not charge again
        self.assertTrue(ingest(self.client).json().get("duplicate"))
        deliver(Signal.objects.get())
        self.paid.profile.refresh_from_db()
        self.assertEqual((self.paid.profile.credits, SignalDelivery.objects.count()), (2, 1))
        web_login(self.client, "paid")
        rows = self.client.get(reverse("signal_feed")).json()["items"]
        self.assertEqual([x["symbol"] for x in rows], ["XAUUSD"])
        self.assertIn("XAUUSD", self.client.get(reverse("dashboard")).content.decode())

    def test_credits_run_out_and_delivery_stops(self):
        for i in range(4):
            ingest(self.client, id=f"s{i}")
        self.paid.profile.refresh_from_db()
        self.assertEqual(self.paid.profile.credits, 0)
        self.assertEqual(SignalDelivery.objects.filter(user=self.paid).count(), 3)

    def test_offline_user_catches_up_and_cursor_works(self):
        for i in range(3):
            ingest(self.client, id=f"s{i}")
        web_login(self.client, "paid")
        first = self.client.get(reverse("signal_feed") + "?after=0").json()["items"]
        self.assertEqual(len(first), 3)
        last = max(x["id"] for x in first)
        ingest(self.client, id="later")      # no credits left, so this one is not delivered
        self.assertEqual(self.client.get(reverse("signal_feed") + f"?after={last}").json()["items"], [])

    def test_late_buyer_gets_no_historical_signals(self):
        ingest(self.client)
        late = make("late")
        give(late, 5)
        web_login(self.client, "late")
        self.assertEqual(self.client.get(reverse("signal_feed")).json()["items"], [])
        late.profile.refresh_from_db()
        self.assertEqual(late.profile.credits, 5)

    def test_expired_signal_is_not_delivered_and_old_rows_show_expired(self):
        sig = Signal.objects.create(event="signal", side="buy", symbol="XAUUSD", timeframe="60", external_id="old", expires_at=timezone.now() - timedelta(minutes=1))
        self.assertEqual(deliver(sig), 0)
        live = Signal.objects.create(event="signal", side="buy", symbol="BTCUSD", timeframe="60", external_id="live", expires_at=timezone.now() + timedelta(minutes=30))
        self.assertEqual(deliver(live), 1)
        Signal.objects.filter(pk=live.pk).update(expires_at=timezone.now() - timedelta(seconds=1))
        live.refresh_from_db()
        self.assertEqual(signal_status(live), "expired")

    def test_exit_goes_only_to_people_who_got_the_signal(self):
        outsider = make("outsider")
        ingest(self.client)
        give(outsider, 5)                                     # bought credits after the signal: never received this setup
        ingest(self.client, event="exit", id="x1", reason="tp")
        self.assertTrue(SignalDelivery.objects.filter(user=self.paid, signal__event="exit").exists())
        self.assertFalse(SignalDelivery.objects.filter(user=outsider).exists())
        self.assertFalse(SignalDelivery.objects.filter(user=self.unpaid).exists())

    def test_staff_never_receive_customer_signals(self):
        agent = make("agt", "agent")
        give(agent, 5)
        ingest(self.client)
        self.assertFalse(SignalDelivery.objects.filter(user=agent).exists())

    def test_ack_is_not_read_and_users_cannot_touch_others(self):
        ingest(self.client)
        d = SignalDelivery.objects.get()
        web_login(self.client, "unpaid")
        self.client.post(reverse("signal_ack"), json.dumps({"ids": [d.id]}), content_type="application/json")
        self.client.post(reverse("signal_read"), json.dumps({"ids": [d.id]}), content_type="application/json")
        d.refresh_from_db()
        self.assertEqual((d.acknowledged_at, d.read_at), (None, None))
        web_login(self.client, "paid")
        self.client.post(reverse("signal_ack"), json.dumps({"ids": [d.id]}), content_type="application/json")
        d.refresh_from_db()
        self.assertIsNotNone(d.acknowledged_at)
        self.assertIsNone(d.read_at)                          # acknowledged by the dashboard, not read by the user
        self.client.post(reverse("signal_read"), json.dumps({"ids": [d.id]}), content_type="application/json")
        d.refresh_from_db()
        self.assertIsNotNone(d.read_at)

    def test_signal_delivery_never_creates_an_order(self):
        ingest(self.client)
        self.assertEqual(Execution.objects.count(), 0)

    def test_ingest_needs_the_secret(self):
        r = self.client.post(reverse("api_ingest"), data="{}", content_type="application/json", HTTP_X_WEBHOOK_SECRET="wrong")
        self.assertEqual(r.status_code, 401)


class PaymentsGateAccess(TestCase):
    def test_pending_order_gives_nothing_and_fulfil_is_idempotent(self):
        from orders.views import fulfill
        u = make("buyer")
        o = Order.objects.create(user=u, product="signals", quantity=10, amount_usd=10, status="pending", reference="r")
        u.profile.refresh_from_db()
        self.assertEqual(u.profile.credits, 0)                # creating/submitting an order grants nothing
        self.assertTrue(fulfill(o, note="webhook"))
        self.assertFalse(fulfill(o, note="duplicate webhook"))
        u.profile.refresh_from_db()
        self.assertEqual((u.profile.credits, u.profile.purchased), (10, 10))

    def test_customer_cannot_approve_own_order(self):
        u = make("buyer2")
        o = Order.objects.create(user=u, product="signals", quantity=10, amount_usd=10, status="pending", reference="r")
        web_login(self.client, "buyer2")
        self.client.post(reverse("staff_order_decide", args=[o.id]), {"action": "approve"})
        o.refresh_from_db(); u.profile.refresh_from_db()
        self.assertEqual((o.status, u.profile.credits), ("pending", 0))


def mt5_conn(user, login="123456", server="Exness-MT5Real"):
    c = BrokerConnection(user=user, broker="exness")
    c.set_credentials(login, TOKEN, {"server": server, "bridge_url": "http://pc:5055"})
    c.save()
    return c


def beat(client, conn, token=TOKEN, **over):
    p = {"terminal_connected": True, "login": "123456", "server": "Exness-MT5Real", "trade_allowed": True, "trade_mode": "demo", "balance": 1000, "equity": 1001}
    p.update(over)
    return client.post(reverse("bot_api_heartbeat"), json.dumps(p), content_type="application/json", HTTP_X_CONNECTION_ID=str(conn.id), HTTP_X_BRIDGE_TOKEN=token)


class MT5Status(TestCase):
    def setUp(self):
        self.u = make("trader")
        self.conn = mt5_conn(self.u)
        from bots import health
        self.health = health

    def state(self):
        self.conn.refresh_from_db()
        return self.health.state(self.conn)

    def test_not_configured_then_connecting_then_connected(self):
        other = make("nobody")
        self.assertEqual(self.health.state(BrokerConnection(user=other, broker="exness")), "not_configured")
        self.assertEqual(self.state(), "connecting")          # saved credentials alone prove nothing
        self.assertEqual(beat(self.client, self.conn).json()["state"], "connected")
        self.assertEqual(self.state(), "connected")

    def test_unauthenticated_or_unknown_heartbeats_are_rejected_identically(self):
        a = beat(self.client, self.conn, token="wrong")
        b = self.client.post(reverse("bot_api_heartbeat"), "{}", content_type="application/json", HTTP_X_CONNECTION_ID="99999", HTTP_X_BRIDGE_TOKEN=TOKEN)
        self.assertEqual((a.status_code, b.status_code, a.content, b.content), (401, 401, b.content, a.content))
        self.assertEqual(self.state(), "connecting")

    def test_identity_mismatch_is_degraded_not_connected(self):
        beat(self.client, self.conn, login="999999")
        self.assertEqual(self.state(), "degraded")
        self.conn.refresh_from_db()
        self.assertFalse(self.conn.identity_verified)
        self.assertEqual(self.conn.error_code, "account_mismatch")

    def test_auth_failure_and_terminal_down(self):
        beat(self.client, self.conn, terminal_connected=False, login=None, error_code="auth_failed", error="Authorization failed (-6) <script>")
        self.assertEqual(self.state(), "auth_failed")
        self.assertNotIn("<", self.conn.last_error)           # untrusted text is reduced to plain characters
        beat(self.client, self.conn, terminal_connected=False, login=None, error_code="terminal_disconnected")
        self.assertEqual(self.state(), "degraded")

    def test_stale_heartbeats_degrade_then_disconnect(self):
        beat(self.client, self.conn)
        BrokerConnection.objects.filter(pk=self.conn.pk).update(last_heartbeat=timezone.now() - timedelta(seconds=150))
        self.assertEqual(self.state(), "degraded")
        BrokerConnection.objects.filter(pk=self.conn.pk).update(last_heartbeat=timezone.now() - timedelta(seconds=900))
        self.assertEqual(self.state(), "disconnected")

    def test_connected_is_not_the_same_as_ready(self):
        beat(self.client, self.conn, trade_allowed=False)
        self.conn.refresh_from_db()
        bot, _ = BotSettings.objects.get_or_create(user=self.u)
        self.assertEqual(self.health.state(self.conn), "connected")
        self.assertFalse(self.health.readiness(self.conn, bot)["ready"])
        beat(self.client, self.conn, trade_allowed=True)
        self.conn.refresh_from_db()
        self.assertFalse(self.health.readiness(self.conn, bot)["ready"])      # still off until the customer enables the bot for MT5
        bot.enabled, bot.broker = True, "exness"
        bot.save()
        self.assertTrue(self.health.readiness(self.conn, bot)["ready"])
        bot.kill_switch = True
        bot.save()
        self.assertFalse(self.health.readiness(self.conn, bot)["ready"])

    def test_dashboard_and_admin_show_status_without_secrets(self):
        beat(self.client, self.conn)
        self.u.profile.refresh_from_db()
        self.u.profile.extend_bot_access(30)
        web_login(self.client, "trader")
        page = self.client.get(reverse("bot_dashboard")).content.decode()
        self.assertTrue("MT5 connection" in page and "Connected" in page, "connection card missing")
        self.assertNotIn(TOKEN, page)
        owner = make("owner", superuser=True)
        web_login(self.client, "owner")
        r = self.client.get(reverse("staff_connections"))
        html = r.content.decode()
        self.assertEqual(r.status_code, 200)
        self.assertIn("Connected", html)
        self.assertIn("•••456", html)                         # masked login
        self.assertNotIn("123456", html.replace("•••456", ""))
        self.assertNotIn(TOKEN, html)
        self.assertIn("trader", self.client.get(reverse("staff_connections") + "?filter=connected").content.decode())
        self.assertNotIn("trader@", self.client.get(reverse("staff_connections") + "?filter=errors").content.decode())

    def test_admin_filters_paid_and_unpaid(self):
        paid = make("rich")
        give(paid, 4)
        make("owner", superuser=True)
        web_login(self.client, "owner")
        paid_html = self.client.get(reverse("staff_connections") + "?filter=paid").content.decode()
        unpaid_html = self.client.get(reverse("staff_connections") + "?filter=unpaid").content.decode()
        self.assertIn("rich", paid_html)
        self.assertNotIn("rich@", unpaid_html)
        self.assertIn("trader", unpaid_html)

    def test_customers_cannot_open_the_admin_overview(self):
        web_login(self.client, "trader")
        self.assertEqual(self.client.get(reverse("staff_connections")).status_code, 302)
