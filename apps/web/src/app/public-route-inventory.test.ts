import { existsSync, readFileSync } from "node:fs";
import path from "node:path";
import { describe, expect, it } from "vitest";

const appDirectory = path.resolve(process.cwd(), "src/app");
const publicPages = [
  "page.tsx",
  "sets/page.tsx",
  "sets/[slug]/page.tsx",
  "regions/page.tsx",
  "regions/[slug]/page.tsx",
  "retailers/page.tsx",
  "retailers/[slug]/page.tsx",
  "batches/page.tsx",
  "batches/[code]/page.tsx",
  "methodology/page.tsx",
  "sources/page.tsx",
  "status/page.tsx",
] as const;

describe("public App Router inventory", () => {
  it("implements every required public page through the aggregate dashboard loader", () => {
    const missing = publicPages.filter((file) => !existsSync(path.join(appDirectory, file)));
    expect(missing).toEqual([]);
    if (missing.length > 0) return;

    for (const file of publicPages) {
      const source = readFileSync(path.join(appDirectory, file), "utf8");
      expect(source, file).toContain("loadDashboard");
      expect(source, file).not.toMatch(/@\/data\/(demo|schema|rpc)|DEMO_(PUBLIC_)?DATA/);
    }
  });
});
