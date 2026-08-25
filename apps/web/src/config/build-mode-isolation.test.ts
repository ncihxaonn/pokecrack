import { existsSync, readFileSync } from "node:fs";
import { resolve } from "node:path";

import { describe, expect, it } from "vitest";

describe("data-mode build isolation", () => {
  it("clears prior prerendered output before every production build", () => {
    const packageJson = JSON.parse(readFileSync(resolve(process.cwd(), "package.json"), "utf8"));
    expect(packageJson.scripts.build).toContain("clean-next.mjs");
    expect(existsSync(resolve(process.cwd(), "scripts/clean-next.mjs"))).toBe(true);
  });

  it("reads every build-relevant environment variable explicitly", () => {
    const source = readFileSync(resolve(process.cwd(), "src/config/env.ts"), "utf8");
    expect(source).toContain("DATA_MODE: process.env.DATA_MODE");
    expect(source).toContain("NEXT_PUBLIC_SUPABASE_URL: process.env.NEXT_PUBLIC_SUPABASE_URL");
  });
});
