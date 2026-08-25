import { describe, expect, it } from "vitest";

import { parseEnv } from "@/config/env";
import { evaluateAdminAccess } from "./policy";

describe("evaluateAdminAccess", () => {
  it("denies by default without a Supabase user", () => {
    const decision = evaluateAdminAccess({
      env: parseEnv({}),
      email: null,
    });

    expect(decision).toEqual({ authorized: false, reason: "no-session" });
  });

  it("denies authenticated users when the server-side allowlist is empty", () => {
    expect(
      evaluateAdminAccess({ env: parseEnv({}), email: "owner@example.com" }),
    ).toEqual({ authorized: false, reason: "allowlist-empty" });
  });

  it("compares allowlisted email addresses case-insensitively", () => {
    const env = parseEnv({ ADMIN_EMAILS: "owner@example.com" });

    expect(evaluateAdminAccess({ env, email: "Owner@Example.com" })).toEqual({
      authorized: true,
      reason: "allowlisted",
      email: "owner@example.com",
    });
    expect(evaluateAdminAccess({ env, email: "other@example.com" })).toEqual({
      authorized: false,
      reason: "email-not-allowed",
    });
  });

  it("never permits an environment-based demo bypass", () => {
    const env = parseEnv({ IGNORED_LEGACY_TOGGLE: "true", NODE_ENV: "test" });

    expect(evaluateAdminAccess({ env, email: null })).toEqual({
      authorized: false,
      reason: "no-session",
    });
  });
});
