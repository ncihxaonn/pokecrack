import { existsSync, readFileSync, readdirSync } from "node:fs";
import path from "node:path";
import { describe, expect, it } from "vitest";

const webRoot = path.resolve(process.cwd());
const routes = [
  "src/app/admin/login/page.tsx",
  "src/app/admin/(protected)/page.tsx",
  "src/app/admin/(protected)/sources/page.tsx",
  "src/app/admin/(protected)/jobs/page.tsx",
  "src/app/admin/(protected)/browser/page.tsx",
  "src/app/admin/(protected)/ai-usage/page.tsx",
  "src/app/admin/(protected)/system/page.tsx",
] as const;

function runtimeSources(directory: string): string[] {
  if (!existsSync(directory)) return [];
  return readdirSync(directory, { withFileTypes: true }).flatMap((entry) => {
    const file = path.join(directory, entry.name);
    if (entry.isDirectory()) return runtimeSources(file);
    return /\.(ts|tsx)$/.test(entry.name) && !entry.name.includes(".test.") ? [file] : [];
  });
}

describe("admin App Router inventory", () => {
  it("provides only login and the six protected operational routes", () => {
    const missing = routes.filter((file) => !existsSync(path.join(webRoot, file)));
    expect(missing).toEqual([]);
    expect(existsSync(path.join(webRoot, "src/app/admin/signup/page.tsx"))).toBe(false);
    expect(existsSync(path.join(webRoot, "src/app/admin/review/page.tsx"))).toBe(false);
  });

  it("guards the protected layout and Next.js proxy", () => {
    const layout = path.join(webRoot, "src/app/admin/(protected)/layout.tsx");
    const proxy = path.join(webRoot, "src/proxy.ts");
    expect(existsSync(layout)).toBe(true);
    expect(existsSync(proxy)).toBe(true);
    if (!existsSync(layout) || !existsSync(proxy)) return;
    expect(readFileSync(layout, "utf8")).toContain("requireAdmin");
    expect(readFileSync(proxy, "utf8")).toContain("/admin/:path*");
  });

  it("contains no runtime demo authentication bypass", () => {
    const files = [
      ...runtimeSources(path.join(webRoot, "src/app/admin")),
      ...runtimeSources(path.join(webRoot, "src/components/admin")),
    ];
    const offenders = files.filter((file) => /adminBypass|admin-bypass/.test(readFileSync(file, "utf8")));
    expect(offenders).toEqual([]);
  });

  it("exposes every control as an authenticated server action", () => {
    const actionsFile = path.join(webRoot, "src/app/admin/(protected)/actions.ts");
    expect(existsSync(actionsFile)).toBe(true);
    if (!existsSync(actionsFile)) return;
    const source = readFileSync(actionsFile, "utf8");
    expect(source.trimStart().startsWith('"use server"')).toBe(true);
    for (const action of [
      "enqueueSourceAction",
      "importCsvAction",
      "importJsonlAction",
      "importOpenCliAction",
      "retryJobAction",
      "cancelJobAction",
      "disableSourceAction",
      "excludeRecordAction",
      "refreshBrowserAction",
      "restartServiceAction",
      "signOutAction",
    ]) {
      expect(source).toContain(`export async function ${action}`);
    }
    expect(source).toContain("requireAdmin");
    expect(source).toContain("parseAdminMutation");
    expect(source).toContain("executeAdminMutation");
    expect(source).toContain("revalidatePath");
    expect(source).toContain("createAdminControlClient");
    expect(source).toContain("process.env.SUPABASE_SERVICE_ROLE_KEY");
    expect(source).toContain("access.userId");
    expect(source).toContain("access.email");
    expect(source).not.toMatch(/NEXT_PUBLIC_[A-Z0-9_]*SERVICE_ROLE/);
  });
});


it("redirects unauthenticated protected admin requests before rendering", () => {
  const source = readFileSync(path.resolve(process.cwd(), "src/proxy.ts"), "utf8");
  expect(source).toContain("/admin/login");
  expect(source).toContain("request.nextUrl.pathname !== \"/admin/login\"");
});
