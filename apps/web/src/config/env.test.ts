import { describe, expect, it } from "vitest";

import { parseEnv } from "./env";

describe("parseEnv", () => {
  it("defaults to demo mode with admin access closed", () => {
    const env = parseEnv({});

    expect(env.dataMode).toBe("demo");
    expect(env.dataMode).toBeDefined();
    expect(env.adminEmails).toEqual([]);
  });

  it("marks live mode unavailable instead of throwing when Supabase is missing", () => {
    const env = parseEnv({ DATA_MODE: "live" });

    expect(env.dataMode).toBe("live");
    expect(env.supabaseConfigured).toBe(false);
  });

  it("normalizes a case-insensitive server-side email allowlist", () => {
    const env = parseEnv({
      ADMIN_EMAILS: " Analyst@Example.com,ops@example.com, analyst@example.com ",
    });

    expect(env.adminEmails).toEqual(["analyst@example.com", "ops@example.com"]);
  });

  it("does not expose an environment-controlled admin bypass", () => {
    const env = parseEnv({ IGNORED_LEGACY_TOGGLE: "true", NODE_ENV: "test" });

    expect(env.dataMode).toBeDefined();
  });

  it("rejects plaintext non-loopback production endpoints", () => {
    expect(() => parseEnv({ NODE_ENV: "production", NEXT_PUBLIC_SITE_URL: "http://data.example.org" })).toThrow(
      /HTTPS/,
    );
    expect(() =>
      parseEnv({
        NODE_ENV: "production",
        DATA_MODE: "live",
        NEXT_PUBLIC_SITE_URL: "https://data.example.org",
        NEXT_PUBLIC_SUPABASE_URL: "http://project.example.org",
        NEXT_PUBLIC_SUPABASE_PUBLISHABLE_KEY: "public-anon-key",
      }),
    ).toThrow(/HTTPS/);
    expect(parseEnv({ NODE_ENV: "production", NEXT_PUBLIC_SITE_URL: "http://127.0.0.1:3000" }).siteUrl).toBe(
      "http://127.0.0.1:3000",
    );
  });

  it("rejects URL credentials, queries, and fragments", () => {
    expect(() =>
      parseEnv({ NEXT_PUBLIC_SITE_URL: "https://user:password@data.example.org" }),
    ).toThrow(/credentials/);
    expect(() =>
      parseEnv({
        DATA_MODE: "live",
        NEXT_PUBLIC_SITE_URL: "https://data.example.org",
        NEXT_PUBLIC_SUPABASE_URL: "https://user:password@project.supabase.co",
        NEXT_PUBLIC_SUPABASE_PUBLISHABLE_KEY: "public-anon-key",
      }),
    ).toThrow(/credentials/);
    expect(() =>
      parseEnv({ NEXT_PUBLIC_SITE_URL: "https://data.example.org/?token=do-not-log" }),
    ).toThrow(/query or fragment/);
    expect(() =>
      parseEnv({ NEXT_PUBLIC_SITE_URL: "https://data.example.org/#private" }),
    ).toThrow(/query or fragment/);
  });

  it("accepts a fully configured live deployment", () => {
    const env = parseEnv({
      DATA_MODE: "live",
      NEXT_PUBLIC_SITE_URL: "https://data.example.org",
      NEXT_PUBLIC_SUPABASE_URL: "https://project.supabase.co",
      NEXT_PUBLIC_SUPABASE_PUBLISHABLE_KEY: "public-anon-key",
    });

    expect(env.dataMode).toBe("live");
    expect(env.siteUrl).toBe("https://data.example.org");
    expect(env.supabaseConfigured).toBe(true);
  });
});
