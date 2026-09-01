import { existsSync, readFileSync } from "node:fs";
import path from "node:path";
import { describe, expect, it } from "vitest";

const appRoot = path.resolve(process.cwd(), "src/app");

describe("SEO metadata routes", () => {
  it("publishes robots, sitemap and an Open Graph image route", () => {
    const expected = ["robots.ts", "sitemap.ts", "opengraph-image.tsx"];
    const missing = expected.filter((file) => !existsSync(path.join(appRoot, file)));
    expect(missing).toEqual([]);
    if (missing.length > 0) return;

    const robots = readFileSync(path.join(appRoot, "robots.ts"), "utf8");
    expect(robots).toContain('"/admin"');
    expect(robots).toContain("/admin/");
    expect(robots).toContain('"/api/internal"');
    expect(robots).toContain("/api/internal/");
    const sitemap = readFileSync(path.join(appRoot, "sitemap.ts"), "utf8");
    expect(sitemap).not.toMatch(/["'`]\/admin/);
    expect(sitemap).toContain("loadDashboard");
  });

  it("sets canonical, Open Graph, Twitter and bounded public revalidation metadata", () => {
    const layout = readFileSync(path.join(appRoot, "layout.tsx"), "utf8");
    expect(layout).toContain("metadataBase");
    expect(layout).toContain("alternates");
    expect(layout).toContain("openGraph");
    expect(layout).toContain("twitter");

    const liveDashboardPages = ["page.tsx"];
    for (const page of liveDashboardPages) expect(readFileSync(path.join(appRoot, page), "utf8"), page).toContain("export const revalidate = 60");

    const researchPages = ["sets/page.tsx", "regions/page.tsx", "retailers/page.tsx", "batches/page.tsx", "methodology/page.tsx"];
    for (const page of researchPages) expect(readFileSync(path.join(appRoot, page), "utf8"), page).toContain("export const revalidate = 900");

    const operationalPages = ["sources/page.tsx", "status/page.tsx"];
    for (const page of operationalPages) expect(readFileSync(path.join(appRoot, page), "utf8"), page).toContain("export const revalidate = 60");

    const sourcesPage = readFileSync(path.join(appRoot, "sources/page.tsx"), "utf8");
    expect(sourcesPage).toContain('createPageMetadata("Sources"');
    expect(sourcesPage).not.toMatch(/Mastodon/);
  });
});
