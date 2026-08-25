import { describe, expect, it } from "vitest";

import nextConfig from "../../next.config";

describe("production security headers", () => {
  it("applies the same browser hardening outside Vercel", async () => {
    expect(nextConfig.headers).toBeTypeOf("function");
    const rules = await nextConfig.headers!();
    const headers = Object.fromEntries(rules.flatMap((rule) => rule.headers.map((header) => [header.key.toLowerCase(), header.value])));
    expect(headers["content-security-policy"]).toContain("frame-ancestors 'none'");
    expect(headers["x-content-type-options"]).toBe("nosniff");
    expect(headers["referrer-policy"]).toBe("strict-origin-when-cross-origin");
    expect(headers["permissions-policy"]).toContain("camera=()");
  });
});
