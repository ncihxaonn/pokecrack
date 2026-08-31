import { readFileSync } from "node:fs";
import { resolve } from "node:path";
import { beforeEach, describe, expect, it, vi } from "vitest";

const mocks = vi.hoisted(() => ({ rpc: vi.fn() }));

vi.mock("@supabase/supabase-js", () => ({
  createClient: () => ({ rpc: mocks.rpc }),
}));
vi.mock("@/config/env", () => ({
  getEnv: () => ({
    dataMode: "live",
    supabaseUrl: "https://project.supabase.co",
    supabasePublishableKey: "public-key",
    supabaseConfigured: true,
  }),
}));
vi.mock("./resolver", () => ({
  resolveDashboardData: async (_env: unknown, loadLive: () => Promise<unknown>) =>
    loadLive(),
}));

import { getDashboardData } from "./server";

const source = readFileSync(resolve(process.cwd(), "src/data/server.ts"), "utf8");

describe("public live-data client", () => {
  beforeEach(() => mocks.rpc.mockReset());

  it("uses a cookie-free publishable client so public routes remain ISR-cacheable", () => {
    expect(source).toContain("createClient");
    expect(source).not.toContain("next/headers");
    expect(source).not.toContain("createServerClient");
  });

  it("keeps the valid v3 snapshot when supplemental coverage rejects", async () => {
    const snapshot = { mode: "live", marker: "valid-v3" };
    mocks.rpc
      .mockResolvedValueOnce({ data: snapshot, error: null })
      .mockRejectedValueOnce(new Error("coverage transport failed"))
      .mockRejectedValueOnce(new Error("social transport failed"));

    await expect(getDashboardData()).resolves.toBe(snapshot);
    expect(mocks.rpc.mock.calls.map(([rpc]) => rpc)).toEqual([
      "get_public_dashboard_snapshot_v3",
      "get_public_study_coverage_v1",
      "get_public_social_discovery_v2",
    ]);
  });
});
