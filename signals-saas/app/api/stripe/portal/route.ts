import { prisma } from "@/lib/prisma";
import { requireApi } from "@/lib/session";
import { stripe, stripeConfigured } from "@/lib/stripe";
import { jsonError } from "@/lib/utils";

export const dynamic = "force-dynamic";

/** POST /api/stripe/portal -> { url }  Stripe customer portal (cancel / update card). */
export async function POST() {
  const { user, error } = await requireApi();
  if (!user) return error;
  if (!stripeConfigured()) return jsonError("Card payments are not enabled.", 503);
  const me = await prisma.user.findUniqueOrThrow({ where: { id: user.id } });
  if (!me.stripeCustomerId) return jsonError("No Stripe customer for this account (manual subscription). Ask support in chat.", 400);
  const session = await stripe().billingPortal.sessions.create({ customer: me.stripeCustomerId, return_url: `${process.env.NEXT_PUBLIC_APP_URL || "http://localhost:3000"}/dashboard/settings` });
  return Response.json({ url: session.url });
}
