import { z } from "zod";

export const TIMEFRAMES = ["5m", "15m", "1h", "4h", "1d"] as const;

export const registerSchema = z.object({
  name: z.string().trim().min(2).max(60),
  email: z.string().trim().email().max(120).transform((e) => e.toLowerCase()),
  password: z.string().min(8).max(128),
});

export const signalWebhookSchema = z
  .object({
    symbol: z.string().trim().min(2).max(20).transform((s) => s.toUpperCase()),
    direction: z.string().transform((d) => d.toUpperCase()).pipe(z.enum(["BUY", "SELL"])),
    entry: z.coerce.number().finite().positive(),
    stopLoss: z.coerce.number().finite().positive(),
    takeProfit: z.coerce.number().finite().positive(),
    timeframe: z.enum(TIMEFRAMES),
    strategy: z.string().trim().max(60).optional(),
  })
  .superRefine((s, ctx) => {
    // stop and target must be on the correct side of the entry
    if (s.direction === "BUY" && !(s.stopLoss < s.entry && s.takeProfit > s.entry)) ctx.addIssue({ code: "custom", message: "BUY needs stopLoss < entry < takeProfit" });
    if (s.direction === "SELL" && !(s.stopLoss > s.entry && s.takeProfit < s.entry)) ctx.addIssue({ code: "custom", message: "SELL needs takeProfit < entry < stopLoss" });
  });

export const signalUpdateSchema = z.object({
  entry: z.coerce.number().positive().optional(),
  stopLoss: z.coerce.number().positive().optional(),
  takeProfit: z.coerce.number().positive().optional(),
  status: z.enum(["ACTIVE", "CLOSED", "CANCELLED"]).optional(),
  result: z.enum(["TP", "SL", "MANUAL"]).optional(),
});

export const messageSchema = z.object({
  body: z.string().trim().max(2000),
  attachmentUrl: z.string().max(300).optional(),
  conversationId: z.string().optional(), // admins target a conversation; users use their own
}).refine((m) => m.body.length > 0 || !!m.attachmentUrl, { message: "empty message" });

export const userActionSchema = z.object({
  action: z.enum(["approve", "ban", "unban", "activate_subscription", "deactivate_subscription", "toggle_autorenew"]),
  months: z.coerce.number().int().min(1).max(24).optional(),
});

export const botSettingsSchema = z.object({
  running: z.boolean().optional(),
  riskPercent: z.coerce.number().min(0.1).max(10).optional(),
  maxDailyLoss: z.coerce.number().min(0.5).max(50).optional(),
  autoExecute: z.boolean().optional(),
  brokerApiKey: z.string().max(500).optional(), // "" clears the key
});

export const accountSchema = z.object({
  name: z.string().trim().min(2).max(60).optional(),
  currentPassword: z.string().optional(),
  newPassword: z.string().min(8).max(128).optional(),
  notifyEmail: z.boolean().optional(),
  notifyBrowser: z.boolean().optional(),
});

export const adminSettingsSchema = z.object({
  action: z.enum(["change_password", "totp_setup", "totp_enable", "totp_disable", "regenerate_webhook_secret"]),
  currentPassword: z.string().optional(),
  newPassword: z.string().min(8).max(128).optional(),
  code: z.string().regex(/^\d{6}$/).optional(),
});
