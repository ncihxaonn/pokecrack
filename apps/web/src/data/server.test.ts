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
      "get_public_social_discovery_v3",
    ]);
  });

  it("does not merge a stale two-source v2 response", async () => {
    const oldV2Payload = {
      schemaVersion: "2.0.0",
      sources: [
        {
          id: "bluesky_jetstream",
          name: "Bluesky Jetstream discovery",
          kind: "social",
          access: "public",
          status: "operational",
          lastCollectedAt: "2026-08-30T10:45:00Z",
          url: "https://bsky.network/docs/jetstream/",
          note: "Public activity discovery only.",
        },
        {
          id: "nostr_multi_relay",
          name: "Nostr multi-relay discovery",
          kind: "social",
          access: "public",
          status: "operational",
          lastCollectedAt: "2026-08-31T02:15:00Z",
          url: "https://github.com/nostr-protocol/nips/blob/master/01.md",
          note: "Public activity discovery only.",
        },
      ],
    };
    mocks.rpc
      .mockResolvedValueOnce({ data: DEMO_PUBLIC_DATA, error: null })
      .mockResolvedValueOnce({ data: null, error: { message: "coverage unavailable" } })
      .mockResolvedValueOnce({ data: oldV2Payload, error: null });

    await expect(getDashboardData()).resolves.toBe(DEMO_PUBLIC_DATA);
  });

  it("merges a delayed Mastodon source without inventing activity metrics", async () => {
    const mastodonSource = {
      id: "mastodon_public_hashtag",
      name: "Mastodon public hashtag discovery",
      kind: "social",
      access: "public",
      status: "delayed",
      lastCollectedAt: null,
      url: "https://docs.joinmastodon.org/methods/timelines/",
      note: "Public hashtag activity discovery only; never opening evidence or a pull-rate denominator.",
    };
    mocks.rpc
      .mockResolvedValueOnce({ data: DEMO_PUBLIC_DATA, error: null })
      .mockResolvedValueOnce({ data: null, error: { message: "coverage unavailable" } })
      .mockResolvedValueOnce({
        data: {
          schemaVersion: "3.0.0",
          sources: [
            {
              id: "bluesky_jetstream",
              name: "Bluesky Jetstream discovery",
              kind: "social",
              access: "public",
              status: "operational",
              lastCollectedAt: "2026-08-30T10:45:00Z",
              url: "https://bsky.network/docs/jetstream/",
              note: "Public activity discovery only.",
            },
            {
              id: "nostr_multi_relay",
              name: "Nostr multi-relay discovery",
              kind: "social",
              access: "public",
              status: "operational",
              lastCollectedAt: "2026-08-31T02:15:00Z",
              url: "https://github.com/nostr-protocol/nips/blob/master/01.md",
              note: "Public activity discovery only.",
            },
            mastodonSource,
          ],
        },
        error: null,
    });

    const result = await getDashboardData();
    expect(result).not.toBe(DEMO_PUBLIC_DATA);
    const merged = result as unknown as { sources: readonly unknown[] };
    expect(merged.sources.at(-1)).toEqual(mastodonSource);
  });
});
