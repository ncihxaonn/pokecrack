import { describe, expect, it } from "vitest";
import nextConfig from "../../next.config";

async function headersFor(path: string) {
  const rules = await nextConfig.headers!();
  return Object.fromEntries(rules.filter(rule => rule.source === "/:path*" || rule.source === path)
    .flatMap(rule => rule.headers.map(header => [header.key.toLowerCase(), header.value])));
}
describe("production security headers", () => {
  it("keeps application pages and the reference document protected against framing", async () => {
    for (const path of ["/", "/sets", "/landing-pages/kage-reference.html"]) {
      const headers = await headersFor(path);
      expect(headers["content-security-policy"]).toContain("frame-ancestors 'none'");
      expect(headers["x-frame-options"]).toBe("DENY");
      expect(headers["x-content-type-options"]).toBe("nosniff");
      expect(headers["referrer-policy"]).toBe("strict-origin-when-cross-origin");
      expect(headers["permissions-policy"]).toContain("camera=()");
    }
  });
  it("allows only the dedicated journey to be framed by the same origin", async () => {
    const headers = await headersFor("/landing-pages/pokemon-kage.html");
    expect(headers["content-security-policy"]).toContain("frame-ancestors 'self'");
    expect(headers["content-security-policy"]).not.toContain("unsafe-eval");
    expect(headers["x-frame-options"]).toBe("SAMEORIGIN");
    expect(headers["x-content-type-options"]).toBe("nosniff");
    expect(headers["permissions-policy"]).toContain("camera=()");
  });
});
