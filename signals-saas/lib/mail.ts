import nodemailer from "nodemailer";

/** Sends e-mail through SMTP_* from .env. If SMTP is not configured the message is logged instead of sent. */
export async function sendMail(to: string, subject: string, html: string): Promise<boolean> {
  const { SMTP_HOST, SMTP_USER, SMTP_PASS, SMTP_FROM, SMTP_PORT } = process.env;
  if (!SMTP_HOST || !SMTP_FROM) {
    console.log(`[mail:disabled] to=${to} subject=${subject}`);
    return false;
  }
  const transport = nodemailer.createTransport({
    host: SMTP_HOST,
    port: Number(SMTP_PORT || 587),
    secure: Number(SMTP_PORT || 587) === 465,
    auth: SMTP_USER ? { user: SMTP_USER, pass: SMTP_PASS } : undefined,
  });
  try {
    await transport.sendMail({ from: SMTP_FROM, to, subject, html });
    return true;
  } catch (e) {
    console.error("[mail] failed:", e);
    return false;
  }
}

export function approvalEmail(name: string | null, appUrl: string) {
  return {
    subject: "Your account has been approved",
    html: `<p>Hi ${name || "there"},</p><p>Your AxeAlgo account is approved. You can now log in and see live signals:</p><p><a href="${appUrl}/login">${appUrl}/login</a></p><p>Trading involves risk; every signal carries a stop-loss for a reason.</p>`,
  };
}
