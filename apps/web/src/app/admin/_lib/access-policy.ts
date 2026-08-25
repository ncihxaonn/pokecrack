import type { AppEnv } from "@/config/env";

export interface AdminUserLike {
  readonly id?: string | null;
  readonly email?: string | null;
  readonly hasAdminClaim?: boolean;
}

export type AdminAccessDecision =
  | { readonly kind: "allowed"; readonly via: "supabase"; readonly email: string; readonly userId: string }
  | { readonly kind: "unauthenticated" }
  | { readonly kind: "forbidden"; readonly email: string | null };

export type AllowedAdminAccess = Extract<AdminAccessDecision, { kind: "allowed" }>;

export class AdminForbiddenError extends Error {
  readonly status = 403;
  readonly code = "ADMIN_FORBIDDEN";
  readonly digest = "NEXT_HTTP_ERROR_FALLBACK;403";

  constructor() {
    super("ADMIN_FORBIDDEN");
    this.name = "AdminForbiddenError";
  }
}

export class AdminUnauthenticatedError extends Error {
  readonly status = 401;
  readonly code = "ADMIN_UNAUTHENTICATED";

  constructor() {
    super("ADMIN_UNAUTHENTICATED: a verified admin session is required");
    this.name = "AdminUnauthenticatedError";
  }
}

export function normalizeAdminEmail(email: string | null | undefined): string | null {
  const normalized = email?.trim().toLocaleLowerCase("en-AU") ?? "";
  return normalized || null;
}

const PROTECTED_ADMIN_PATHS = new Set([
  "/admin",
  "/admin/sources",
  "/admin/jobs",
  "/admin/browser",
  "/admin/ai-usage",
  "/admin/system",
]);

export function sanitizeAdminReturnPath(value: unknown): string {
  const candidate = Array.isArray(value) ? value[0] : value;
  if (typeof candidate !== "string") return "/admin";

  try {
    const parsed = new URL(candidate, "https://admin.invalid");
    if (parsed.origin !== "https://admin.invalid" || !PROTECTED_ADMIN_PATHS.has(parsed.pathname)) return "/admin";
    return `${parsed.pathname}${parsed.search}${parsed.hash}`;
  } catch {
    return "/admin";
  }
}

export function evaluateAdminAccess(env: AppEnv, user: AdminUserLike | null): AdminAccessDecision {
  if (!env.supabaseConfigured || user === null) return { kind: "unauthenticated" };

  const email = normalizeAdminEmail(user.email);
  const userId = user.id?.trim().toLowerCase() ?? "";
  const hasStableUserId = /^[0-9a-f]{8}-[0-9a-f]{4}-[1-5][0-9a-f]{3}-[89ab][0-9a-f]{3}-[0-9a-f]{12}$/.test(userId);
  if (
    email
    && hasStableUserId
    && user.hasAdminClaim === true
    && env.adminEmails.includes(email)
  ) return { kind: "allowed", via: "supabase", email, userId };
  return { kind: "forbidden", email };
}

export function enforceAdminAccess(decision: AdminAccessDecision): AllowedAdminAccess {
  if (decision.kind === "allowed") return decision;
  if (decision.kind === "forbidden") throw new AdminForbiddenError();
  throw new AdminUnauthenticatedError();
}
