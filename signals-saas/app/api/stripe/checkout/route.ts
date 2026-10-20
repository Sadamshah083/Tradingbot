import { prisma } from "@/lib/prisma";
import { requireApi } from "@/lib/session";
import { stripe, stripeConfigured } from "@/lib/stripe";
import { jsonError } from "@/lib/utils";

export const dynamic = "force-dynamic";

/** POST /api/stripe/checkout -> { url }  ($20/month recurring "Trading Bot Access") */
export async function POST() {
  const { user, error } = await requireApi();
  if (!user) return error;
  if (!stripeConfigured()) return jsonError("Card payments are not enabled yet. Contact support in chat for manual activation.", 503);
  const me = await prisma.user.findUniqueOrThrow({ where: { id: user.id } });
  const s = stripe();
  let customerId = me.stripeCustomerId;
  if (!customerId) {
    const customer = await s.customers.create({ email: me.email, name: me.name ?? undefined, metadata: { userId: me.id } });
    customerId = customer.id;
    await prisma.user.update({ where: { id: me.id }, data: { stripeCustomerId: customerId } });
  }
  const appUrl = process.env.NEXT_PUBLIC_APP_URL || "http://localhost:3000";
  const session = await s.checkout.sessions.create({
    mode: "subscription",
    customer: customerId,
    line_items: [{ price: process.env.STRIPE_PRICE_ID!, quantity: 1 }],
    success_url: `${appUrl}/dashboard/bot?success=true`,
    cancel_url: `${appUrl}/dashboard/bot?cancelled=true`,
    metadata: { userId: me.id },
    subscription_data: { metadata: { userId: me.id } },
    allow_promotion_codes: true,
  });
  return Response.json({ url: session.url });
}
