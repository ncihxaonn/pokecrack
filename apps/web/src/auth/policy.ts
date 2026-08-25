import type { AppEnv } from "@/config/env";

export type AdminAccessDecision =
  | {
      readonly authorized: true;
      readonly reason: "allowlisted";
      readonly email: string;
    }
  | {
      readonly authorized: false;
      readonly reason: "no-session" | "allowlist-empty" | "email-not-allowed";
    };

interface AdminAccessInput {
  readonly env: AppEnv;
  readonly email: string | null | undefined;
}

export function evaluateAdminAccess({
  env,
  email,
}: AdminAccessInput): AdminAccessDecision {
  if (!email) return { authorized: false, reason: "no-session" };
  if (env.adminEmails.length === 0) {
    return { authorized: false, reason: "allowlist-empty" };
  }

  const normalizedEmail = email.trim().toLowerCase();
  if (!env.adminEmails.includes(normalizedEmail)) {
    return { authorized: false, reason: "email-not-allowed" };
  }
  return {
    authorized: true,
    reason: "allowlisted",
    email: normalizedEmail,
  };
}
