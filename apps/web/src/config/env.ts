import { z } from "zod";

import { BRAND } from "./brand";

const rawEnvSchema = z
  .object({
    NODE_ENV: z.enum(["development", "test", "production"]).default("development"),
    DATA_MODE: z.enum(["demo", "live"]).default("demo"),
    NEXT_PUBLIC_SITE_URL: z.url().default(BRAND.defaultSiteUrl),
    NEXT_PUBLIC_SUPABASE_URL: z.url().optional(),
    NEXT_PUBLIC_SUPABASE_PUBLISHABLE_KEY: z.string().min(1).optional(),
    NEXT_PUBLIC_SUPABASE_ANON_KEY: z.string().min(1).optional(),
    ADMIN_EMAILS: z.string().default(""),
  })
;

export type DataMode = "demo" | "live";

export interface AppEnv {
  readonly nodeEnv: "development" | "test" | "production";
  readonly dataMode: DataMode;
  readonly siteUrl: string;
  readonly supabaseUrl?: string;
  readonly supabasePublishableKey?: string;
  readonly supabaseConfigured: boolean;
  readonly adminEmails: readonly string[];
}

type RawEnv = Record<string, string | undefined>;

function requiresHttps(url: URL): boolean {
  const hostname = url.hostname.toLowerCase();
  const loopback =
    hostname === "localhost" ||
    hostname.endsWith(".localhost") ||
    hostname === "127.0.0.1" ||
    hostname === "::1";
  return url.protocol !== "https:" && !loopback;
}

export function parseEnv(input: RawEnv): AppEnv {
  const parsed = rawEnvSchema.parse({
    ...input,
    DATA_MODE: input.DATA_MODE ?? input.NEXT_PUBLIC_DATA_MODE,
  });
  for (const [name, value] of [
    ["NEXT_PUBLIC_SITE_URL", parsed.NEXT_PUBLIC_SITE_URL],
    ["NEXT_PUBLIC_SUPABASE_URL", parsed.NEXT_PUBLIC_SUPABASE_URL],
  ] as const) {
    if (!value) continue;
    const url = new URL(value);
    if (url.username || url.password) {
      throw new Error(`${name} must not contain URL credentials`);
    }
    if (url.search || url.hash) {
      throw new Error(`${name} must not contain a query or fragment`);
    }
    if (parsed.NODE_ENV === "production" && requiresHttps(url)) {
      throw new Error(`${name} must use HTTPS outside loopback in production`);
    }
  }
  const adminEmails = [
    ...new Set(
      parsed.ADMIN_EMAILS.split(",")
        .map((email) => email.trim().toLowerCase())
        .filter(Boolean),
    ),
  ];
  const supabasePublishableKey =
    parsed.NEXT_PUBLIC_SUPABASE_PUBLISHABLE_KEY ??
    parsed.NEXT_PUBLIC_SUPABASE_ANON_KEY;

  return {
    nodeEnv: parsed.NODE_ENV,
    dataMode: parsed.DATA_MODE,
    siteUrl: parsed.NEXT_PUBLIC_SITE_URL.replace(/\/$/, ""),
    supabaseUrl: parsed.NEXT_PUBLIC_SUPABASE_URL,
    supabasePublishableKey,
    supabaseConfigured: Boolean(
      parsed.NEXT_PUBLIC_SUPABASE_URL && supabasePublishableKey,
    ),
    adminEmails,
  };
}

export function getEnv(): AppEnv {
  return parseEnv({
    NODE_ENV: process.env.NODE_ENV,
    DATA_MODE: process.env.DATA_MODE,
    NEXT_PUBLIC_DATA_MODE: process.env.NEXT_PUBLIC_DATA_MODE,
    NEXT_PUBLIC_SITE_URL: process.env.NEXT_PUBLIC_SITE_URL,
    NEXT_PUBLIC_SUPABASE_URL: process.env.NEXT_PUBLIC_SUPABASE_URL,
    NEXT_PUBLIC_SUPABASE_PUBLISHABLE_KEY:
      process.env.NEXT_PUBLIC_SUPABASE_PUBLISHABLE_KEY,
    NEXT_PUBLIC_SUPABASE_ANON_KEY: process.env.NEXT_PUBLIC_SUPABASE_ANON_KEY,
    ADMIN_EMAILS: process.env.ADMIN_EMAILS,
  });
}
