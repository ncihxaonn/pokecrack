import { existsSync } from "node:fs";
import path from "node:path";
import { describe, expect, it } from "vitest";

import { parseEnv } from "@/config/env";

const moduleFile = path.resolve(process.cwd(), "src/app/admin/_lib/access-policy.ts");

describe("admin access policy", () => {
  it("never permits a demo bypass and requires configured Supabase authentication", async () => {
    expect(existsSync(moduleFile)).toBe(true);
    if (!existsSync(moduleFile)) return;
    const modulePath = "./access-policy";
    const { evaluateAdminAccess } = await import(/* @vite-ignore */ modulePath);

    expect(evaluateAdminAccess(parseEnv({ DATA_MODE: "demo" }), null)).toEqual({ kind: "unauthenticated" });
    const legacyBypassEnv = parseEnv({
      DATA_MODE: "demo",
      IGNORED_LEGACY_TOGGLE: "true",
      ADMIN_EMAILS: "admin@example.com",
    });
    expect(evaluateAdminAccess(legacyBypassEnv, null)).toEqual({ kind: "unauthenticated" });
    expect(evaluateAdminAccess(legacyBypassEnv, { email: "admin@example.com" })).toEqual({ kind: "unauthenticated" });
  });

  it("normalizes allowlisted email and exposes a 403 error for every other authenticated user", async () => {
    expect(existsSync(moduleFile)).toBe(true);
    if (!existsSync(moduleFile)) return;
    const modulePath = "./access-policy";
    const { AdminForbiddenError, enforceAdminAccess, evaluateAdminAccess } = await import(/* @vite-ignore */ modulePath);
    const env = parseEnv({
      DATA_MODE: "live",
      NEXT_PUBLIC_SUPABASE_URL: "https://project.supabase.co",
      NEXT_PUBLIC_SUPABASE_PUBLISHABLE_KEY: "public-key",
      ADMIN_EMAILS: " Admin@Example.COM ",
    });

    expect(evaluateAdminAccess(env, {
      id: "11111111-1111-4111-8111-111111111111",
      email: " admin@example.com ",
      hasAdminClaim: true,
    })).toMatchObject({ kind: "allowed", email: "admin@example.com" });
    const denied = evaluateAdminAccess(env, { email: "other@example.com" });
    expect(denied).toEqual({ kind: "forbidden", email: "other@example.com" });
    expect(() => enforceAdminAccess(denied)).toThrow(AdminForbiddenError);
    try {
      enforceAdminAccess(denied);
    } catch (error) {
      expect(error).toMatchObject({ status: 403, code: "ADMIN_FORBIDDEN" });
    }
  });

  it("requires a stable Supabase user id and the explicit admin app-metadata claim", async () => {
    const modulePath = "./access-policy";
    const { evaluateAdminAccess } = await import(/* @vite-ignore */ modulePath);
    const env = parseEnv({
      DATA_MODE: "live",
      NEXT_PUBLIC_SUPABASE_URL: "https://project.supabase.co",
      NEXT_PUBLIC_SUPABASE_PUBLISHABLE_KEY: "public-key",
      ADMIN_EMAILS: "admin@example.com",
    });

    expect(evaluateAdminAccess(env, {
      id: "11111111-1111-4111-8111-111111111111",
      email: "admin@example.com",
      hasAdminClaim: false,
    })).toEqual({ kind: "forbidden", email: "admin@example.com" });
    expect(evaluateAdminAccess(env, {
      id: "11111111-1111-4111-8111-111111111111",
      email: "admin@example.com",
      hasAdminClaim: true,
    })).toEqual({
      kind: "allowed",
      via: "supabase",
      email: "admin@example.com",
      userId: "11111111-1111-4111-8111-111111111111",
    });
  });

  it("marks forbidden decisions as an HTTP 403 without rendering an internal error", async () => {
    const modulePath = "./access-policy";
    const { enforceAdminAccess } = await import(/* @vite-ignore */ modulePath);

    try {
      enforceAdminAccess({ kind: "forbidden", email: "other@example.com" });
      throw new Error("expected forbidden decision to throw");
    } catch (error) {
      expect(error).toMatchObject({
        digest: "NEXT_HTTP_ERROR_FALLBACK;403",
        status: 403,
        message: "ADMIN_FORBIDDEN",
      });
    }
  });

  it("allows return navigation only to the known protected admin routes", async () => {
    const modulePath = "./access-policy";
    const { sanitizeAdminReturnPath } = await import(/* @vite-ignore */ modulePath);

    expect(sanitizeAdminReturnPath("/admin/jobs?status=dead")).toBe("/admin/jobs?status=dead");
    expect(sanitizeAdminReturnPath("/administrator")).toBe("/admin");
    expect(sanitizeAdminReturnPath("//attacker.invalid/admin")).toBe("/admin");
    expect(sanitizeAdminReturnPath("/admin/login?next=/admin/login")).toBe("/admin");
  });
});
