import { readFileSync } from "node:fs";
import { resolve } from "node:path";
import { describe, expect, it } from "vitest";

const source = readFileSync(resolve(process.cwd(), "src/app/_lib/dashboard.ts"), "utf8");

describe("public dashboard cache", () => {
  it("uses a one-minute shared ISR cache for the live public snapshot", () => {
    expect(source).toContain("unstable_cache");
    expect(source).toContain('"public-dashboard-v3-coverage-v2-social-v4-live60"');
    expect(source).not.toContain('"public-dashboard-v3-coverage-v2-social-v3-live60"');
    expect(source).toContain("revalidate: 60");
    expect(source).toContain('tags: ["public-dashboard"]');
  });
});
