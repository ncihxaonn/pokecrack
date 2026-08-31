import { describe, expect, it } from "vitest";

import { DEMO_PUBLIC_DATA } from "./demo";
import {
  mergePublicSocialDiscovery,
  publicSocialDiscoverySchema,
} from "./social-discovery";

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

describe("public social discovery supplement", () => {
  it("accepts the exact public-safe Bluesky and Nostr identities and appends them", () => {
    const payload = {
      schemaVersion: "2.0.0",
      sources: [blueskySource, nostrSource],
    };

    expect(publicSocialDiscoverySchema.parse(payload)).toEqual(payload);
    const merged = mergePublicSocialDiscovery(DEMO_PUBLIC_DATA, payload);

    expect(merged).toMatchObject({
      sources: expect.arrayContaining([blueskySource, nostrSource]),
    });
  });

  it("fails closed on identity drift, private fields, and source collisions", () => {
    const drifted = {
      schemaVersion: "2.0.0",
      sources: [
        blueskySource,
        { ...nostrSource, url: "https://example.com/stream" },
      ],
    };
    const privatePayload = {
      schemaVersion: "2.0.0",
      sources: [
        blueskySource,
        { ...nostrSource, eventId: "private", pubkey: "private" },
      ],
    };
    const collision = {
      ...DEMO_PUBLIC_DATA,
      sources: [...DEMO_PUBLIC_DATA.sources, nostrSource],
    };

    expect(mergePublicSocialDiscovery(DEMO_PUBLIC_DATA, drifted)).toBe(
      DEMO_PUBLIC_DATA,
    );
    expect(mergePublicSocialDiscovery(DEMO_PUBLIC_DATA, privatePayload)).toBe(
      DEMO_PUBLIC_DATA,
    );
    expect(
      mergePublicSocialDiscovery(collision, {
        schemaVersion: "2.0.0",
        sources: [blueskySource, nostrSource],
      }),
    ).toBe(collision);
  });
});
