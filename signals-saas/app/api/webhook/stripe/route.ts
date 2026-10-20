import type Stripe from "stripe";
import { prisma } from "@/lib/prisma";
import { stripe } from "@/lib/stripe";
import { emitToAdmins, emitToUser } from "@/lib/socket";

export const dynamic = "force-dynamic";

/**
 * POST /api/webhook/stripe  (Stripe -> us). Verified with STRIPE_WEBHOOK_SECRET.
 * checkout.session.completed / invoice.paid  -> ACTIVE, expiry = period end (fallback now + 30 days)
 * invoice.payment_failed / customer.subscription.deleted -> EXPIRED (3-day grace handled by hasBotAccess)
 */
export async function POST(req: Request) {
  const sig = req.headers.get("stripe-signature");
  const secret = process.env.STRIPE_WEBHOOK_SECRET;
  if (!sig || !secret) return Response.json({ error: "webhook not configured" }, { status: 400 });
  let event: Stripe.Event;
  try {
    event = stripe().webhooks.constructEvent(await req.text(), sig, secret);
  } catch (e) {
    return Response.json({ error: `signature verification failed: ${(e as Error).message}` }, { status: 400 });
  }

  const activate = async (customerId: string | null, subscriptionId: string | null, periodEnd?: number | null) => {
    if (!customerId) return;
    const user = await prisma.user.findFirst({ where: { stripeCustomerId: customerId } });
    if (!user) return;
    const expiry = periodEnd ? new Date(periodEnd * 1000) : new Date(Date.now() + 30 * 86400e3);
    await prisma.user.update({ where: { id: user.id }, data: { subscriptionStatus: "ACTIVE", subscriptionExpiry: expiry, stripeSubscriptionId: subscriptionId ?? user.stripeSubscriptionId, autoRenew: true } });
    emitToUser(user.id, "account:update", { subscriptionStatus: "ACTIVE" });
    emitToAdmins("user:update", { id: user.id, subscriptionStatus: "ACTIVE", subscriptionExpiry: expiry });
  };
  const expire = async (customerId: string | null) => {
    if (!customerId) return;
    const user = await prisma.user.findFirst({ where: { stripeCustomerId: customerId } });
    if (!user) return;
    await prisma.user.update({ where: { id: user.id }, data: { subscriptionStatus: "EXPIRED", subscriptionExpiry: user.subscriptionExpiry ?? new Date() } });
    emitToUser(user.id, "account:update", { subscriptionStatus: "EXPIRED" });
    emitToAdmins("user:update", { id: user.id, subscriptionStatus: "EXPIRED" });
  };
  const str = (v: unknown) => (typeof v === "string" ? v : v && typeof v === "object" && "id" in v ? String((v as { id: string }).id) : null);

  switch (event.type) {
    case "checkout.session.completed": {
      const s = event.data.object as Stripe.Checkout.Session;
      await activate(str(s.customer), str(s.subscription));
      break;
    }
    case "invoice.paid": {
      const inv = event.data.object as Stripe.Invoice;
      const periodEnd = inv.lines?.data?.[0]?.period?.end ?? null;
      await activate(str(inv.customer), str(inv.subscription), periodEnd);
      break;
    }
    case "invoice.payment_failed":
    case "customer.subscription.deleted": {
      const obj = event.data.object as Stripe.Invoice | Stripe.Subscription;
      await expire(str(obj.customer));
      break;
    }
    case "customer.subscription.updated": {
      const sub = event.data.object as Stripe.Subscription;
      const user = await prisma.user.findFirst({ where: { stripeCustomerId: str(sub.customer) ?? "" } });
      if (user) await prisma.user.update({ where: { id: user.id }, data: { autoRenew: !sub.cancel_at_period_end, subscriptionExpiry: new Date(sub.current_period_end * 1000) } });
      break;
    }
    default:
      break;
  }
  return Response.json({ received: true });
}
