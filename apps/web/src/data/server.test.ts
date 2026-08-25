import { readFileSync } from "node:fs";
import { resolve } from "node:path";
import { describe, expect, it } from "vitest";

const source = readFileSync(resolve(process.cwd(), "src/data/server.ts"), "utf8");

describe("public live-data client", () => {
  it("uses a cookie-free publishable client so public routes remain ISR-cacheable", () => {
    expect(source).toContain("createClient");
    expect(source).not.toContain("next/headers");
    expect(source).not.toContain("createServerClient");
  });
});
