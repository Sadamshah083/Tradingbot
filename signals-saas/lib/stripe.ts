import Stripe from "stripe";

let _stripe: Stripe | null = null;

/** Lazily constructed so the app runs (with billing disabled) when Stripe is not configured yet. */
export function stripe(): Stripe {
  if (!process.env.STRIPE_SECRET_KEY) throw new Error("STRIPE_SECRET_KEY is not configured");
  if (!_stripe) _stripe = new Stripe(process.env.STRIPE_SECRET_KEY); // SDK default API version
  return _stripe;
}

export const stripeConfigured = () => Boolean(process.env.STRIPE_SECRET_KEY && process.env.STRIPE_PRICE_ID);
export const GRACE_DAYS = 3;

/** Bot access = subscription ACTIVE, or expired less than GRACE_DAYS ago. */
export function hasBotAccess(u: { subscriptionStatus: string; subscriptionExpiry: Date | null }): boolean {
  if (u.subscriptionStatus === "ACTIVE") return true;
  if (u.subscriptionExpiry && Date.now() - u.subscriptionExpiry.getTime() < GRACE_DAYS * 86400e3) return true;
  return false;
}
