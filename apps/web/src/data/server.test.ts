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
const mastodonSource = {
  id: "mastodon_public_hashtag",
  name: "Mastodon public hashtag discovery",
  kind: "social",
  access: "public",
  status: "delayed",
  lastCollectedAt: null,
  url: "https://docs.joinmastodon.org/methods/timelines/",
  note: "Public hashtag activity discovery only; it is never opening evidence, a statistical sample, or a pull-rate denominator.",
} as const;
const v2SocialPayload = {
  schemaVersion: "2.0.0",
  sources: [blueskySource, nostrSource],
} as const;
const v3SocialPayload = {
  schemaVersion: "3.0.0",
  sources: [blueskySource, nostrSource, mastodonSource],
} as const;
const v4SocialPayload = {
  schemaVersion: "4.0.0",
  window: {
    start: "2026-08-30T10:45:00Z",
    end: "2026-08-31T10:45:00Z",
  },
  activityOnly: true,
  nonEvidence: true,
  sources: [
    {
      id: "bluesky_jetstream",
      name: "Bluesky Jetstream discovery",
      kind: "social",
      access: "public",
      status: "operational",
      freshness: "fresh",
      lastCollectedAt: "2026-08-31T10:45:00Z",
      newCandidates24h: 12,
      retainedCandidates: 42,
      activityOnly: true,
      statisticsEligible: false,
    },
    {
      id: "nostr_multi_relay",
      name: "Nostr multi-relay discovery",
      kind: "social",
      access: "public",
      status: "delayed",
      freshness: "delayed",
      lastCollectedAt: "2026-08-31T10:30:00Z",
      newCandidates24h: 8,
      retainedCandidates: 18,
      activityOnly: true,
      statisticsEligible: false,
    },
    {
      id: "mastodon_public_hashtag",
      name: "Mastodon public hashtag discovery",
      kind: "social",
      access: "public",
      status: "attention",
      freshness: "attention",
      lastCollectedAt: null,
      newCandidates24h: 0,
      retainedCandidates: 0,
      activityOnly: true,
      statisticsEligible: false,
    },
  ],
} as const;

describe("public live-data client", () => {
  beforeEach(() => mocks.rpc.mockReset());

  it("uses a cookie-free publishable client so public routes remain ISR-cacheable", () => {
    expect(source).toContain("createClient");
    expect(source).not.toContain("next/headers");
    expect(source).not.toContain("createServerClient");
  });

  it("keeps the valid snapshot when supplemental coverage and social fallbacks reject", async () => {
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
      "get_public_social_discovery_v4",
      "get_public_social_discovery_v3",
    ]);
  });

  it("prefers the v4 social pulse and fetches v3 provenance independently", async () => {
    mocks.rpc
      .mockResolvedValueOnce({ data: DEMO_PUBLIC_DATA, error: null })
      .mockResolvedValueOnce({ data: null, error: null })
      .mockResolvedValueOnce({ data: v4SocialPayload, error: null })
      .mockResolvedValueOnce({ data: v3SocialPayload, error: null });

    const result = await getDashboardData();

    expect(result).toMatchObject({
      socialActivityPulse: v4SocialPayload,
      sources: expect.arrayContaining([blueskySource, nostrSource, mastodonSource]),
    });
    expect(mocks.rpc.mock.calls.map(([rpc]) => rpc)).toEqual([
      "get_public_dashboard_snapshot_v3",
      "get_public_study_coverage_v1",
      "get_public_social_discovery_v4",
      "get_public_social_discovery_v3",
    ]);
  });

  it.each([
    ["returns an RPC error", { data: null, error: { message: "function missing" } }],
    ["rejects during transport", new Error("social transport failed")],
  ] as const)("falls back to the v3 tuple when v4 %s", async (_label, v4Failure) => {
    mocks.rpc
      .mockResolvedValueOnce({ data: DEMO_PUBLIC_DATA, error: null })
      .mockResolvedValueOnce({ data: null, error: null });
    if (v4Failure instanceof Error) {
      mocks.rpc.mockRejectedValueOnce(v4Failure);
    } else {
      mocks.rpc.mockResolvedValueOnce(v4Failure);
    }
    mocks.rpc.mockResolvedValueOnce({ data: v3SocialPayload, error: null });

    const result = await getDashboardData();

    expect(result).toMatchObject({ sources: expect.arrayContaining([blueskySource]) });
    expect((result as unknown as typeof DEMO_PUBLIC_DATA).sources).toEqual(
      expect.arrayContaining([nostrSource, mastodonSource]),
    );
    expect(mocks.rpc.mock.calls.map(([rpc]) => rpc)).toEqual([
      "get_public_dashboard_snapshot_v3",
      "get_public_study_coverage_v1",
      "get_public_social_discovery_v4",
      "get_public_social_discovery_v3",
    ]);
  });

  it("does not fall back when v4 returns data with a malformed payload", async () => {
    mocks.rpc
      .mockResolvedValueOnce({ data: DEMO_PUBLIC_DATA, error: null })
      .mockResolvedValueOnce({ data: null, error: null })
      .mockResolvedValueOnce({
        data: { schemaVersion: "4.0.0", sources: [blueskySource, nostrSource] },
        error: null,
      });

    await expect(getDashboardData()).resolves.toBe(DEMO_PUBLIC_DATA);
    expect(mocks.rpc.mock.calls.map(([rpc]) => rpc)).toEqual([
      "get_public_dashboard_snapshot_v3",
      "get_public_study_coverage_v1",
      "get_public_social_discovery_v4",
    ]);
  });

  it("does not merge a stale two-source v2 response", async () => {
    mocks.rpc
      .mockResolvedValueOnce({ data: DEMO_PUBLIC_DATA, error: null })
      .mockResolvedValueOnce({ data: null, error: { message: "coverage unavailable" } })
      .mockResolvedValueOnce({ data: v2SocialPayload, error: null });

    await expect(getDashboardData()).resolves.toBe(DEMO_PUBLIC_DATA);
  });

  it("merges a delayed Mastodon source without inventing activity metrics", async () => {
    mocks.rpc
      .mockResolvedValueOnce({ data: DEMO_PUBLIC_DATA, error: null })
      .mockResolvedValueOnce({ data: null, error: { message: "coverage unavailable" } })
      .mockResolvedValueOnce({ data: v3SocialPayload, error: null });

    const result = await getDashboardData();
    expect(result).not.toBe(DEMO_PUBLIC_DATA);
    const merged = result as unknown as { sources: readonly unknown[] };
    expect(merged.sources.at(-1)).toEqual(mastodonSource);
  });

  it("preserves dashboard failure semantics when the main RPC rejects", async () => {
    mocks.rpc
      .mockRejectedValueOnce(new Error("dashboard transport failed"))
      .mockResolvedValueOnce({ data: null, error: null })
      .mockResolvedValueOnce({ data: v4SocialPayload, error: null });

    await expect(getDashboardData()).rejects.toThrow("dashboard transport failed");
    expect(mocks.rpc).toHaveBeenCalledTimes(3);
  });
});
