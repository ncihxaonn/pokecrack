import { readFileSync } from "node:fs";
import { resolve } from "node:path";
import { beforeEach, describe, expect, it, vi } from "vitest";

import { DEMO_PUBLIC_DATA } from "./demo";

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
const blueskySource = {
  id: "bluesky_jetstream",
  name: "Bluesky Jetstream discovery",
  kind: "social",
  access: "public",
  status: "operational",
  lastCollectedAt: "2026-08-30T10:45:00Z",
  url: "https://bsky.network/docs/jetstream/",
  note: "42 retained activity candidates. Bounded live coverage only; never opening evidence, geography, a hit, or a pull-rate denominator.",
} as const;
const nostrSource = {
  id: "nostr_multi_relay",
  name: "Nostr multi-relay discovery",
  kind: "social",
  access: "public",
  status: "operational",
  lastCollectedAt: "2026-08-31T02:15:00Z",
  url: "https://github.com/nostr-protocol/nips/blob/master/01.md",
  note: "3 of 3 reviewed public relays collected recently; 18 retained tag-matched activity candidates. Multi-relay coverage can be incomplete and is never opening evidence or a pull-rate denominator.",
} as const;
const v1SocialPayload = {
  schemaVersion: "1.0.0",
  sources: [blueskySource],
} as const;
const v2SocialPayload = {
  schemaVersion: "2.0.0",
  sources: [blueskySource, nostrSource],
} as const;

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
      .mockRejectedValueOnce(new Error("social transport failed"))
      .mockRejectedValueOnce(new Error("social fallback transport failed"));

    await expect(getDashboardData()).resolves.toBe(snapshot);
    expect(mocks.rpc.mock.calls.map(([rpc]) => rpc)).toEqual([
      "get_public_dashboard_snapshot_v3",
      "get_public_study_coverage_v1",
      "get_public_social_discovery_v2",
      "get_public_social_discovery_v1",
    ]);
  });

  it("prefers the v2 social tuple and does not call the v1 fallback", async () => {
    mocks.rpc
      .mockResolvedValueOnce({ data: DEMO_PUBLIC_DATA, error: null })
      .mockResolvedValueOnce({ data: null, error: null })
      .mockResolvedValueOnce({ data: v2SocialPayload, error: null });

    const result = await getDashboardData();

    expect(result).toMatchObject({
      sources: expect.arrayContaining([blueskySource, nostrSource]),
    });
    expect(mocks.rpc.mock.calls.map(([rpc]) => rpc)).toEqual([
      "get_public_dashboard_snapshot_v3",
      "get_public_study_coverage_v1",
      "get_public_social_discovery_v2",
    ]);
  });

  it.each([
    ["returns an RPC error", { data: null, error: { message: "function missing" } }],
    ["rejects during transport", new Error("social transport failed")],
  ] as const)("falls back to the v1 Bluesky-only tuple when v2 %s", async (_label, v2Failure) => {
    mocks.rpc
      .mockResolvedValueOnce({ data: DEMO_PUBLIC_DATA, error: null })
      .mockResolvedValueOnce({ data: null, error: null });
    if (v2Failure instanceof Error) {
      mocks.rpc.mockRejectedValueOnce(v2Failure);
    } else {
      mocks.rpc.mockResolvedValueOnce(v2Failure);
    }
    mocks.rpc.mockResolvedValueOnce({ data: v1SocialPayload, error: null });

    const result = await getDashboardData();

    expect(result).toMatchObject({ sources: expect.arrayContaining([blueskySource]) });
    expect((result as unknown as typeof DEMO_PUBLIC_DATA).sources).not.toEqual(
      expect.arrayContaining([nostrSource]),
    );
    expect(mocks.rpc.mock.calls.map(([rpc]) => rpc)).toEqual([
      "get_public_dashboard_snapshot_v3",
      "get_public_study_coverage_v1",
      "get_public_social_discovery_v2",
      "get_public_social_discovery_v1",
    ]);
  });

  it("does not fall back when v2 returns data with a malformed payload", async () => {
    mocks.rpc
      .mockResolvedValueOnce({ data: DEMO_PUBLIC_DATA, error: null })
      .mockResolvedValueOnce({ data: null, error: null })
      .mockResolvedValueOnce({
        data: { schemaVersion: "2.0.0", sources: [blueskySource] },
        error: null,
      });

    await expect(getDashboardData()).resolves.toBe(DEMO_PUBLIC_DATA);
    expect(mocks.rpc.mock.calls.map(([rpc]) => rpc)).toEqual([
      "get_public_dashboard_snapshot_v3",
      "get_public_study_coverage_v1",
      "get_public_social_discovery_v2",
    ]);
  });

  it("preserves dashboard failure semantics when the main RPC rejects", async () => {
    mocks.rpc
      .mockRejectedValueOnce(new Error("dashboard transport failed"))
      .mockResolvedValueOnce({ data: null, error: null })
      .mockResolvedValueOnce({ data: v2SocialPayload, error: null });

    await expect(getDashboardData()).rejects.toThrow("dashboard transport failed");
    expect(mocks.rpc).toHaveBeenCalledTimes(3);
  });
});
