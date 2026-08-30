import { describe, expect, it } from "vitest";

import { DEMO_PUBLIC_DATA } from "./demo";
import {
  mergePublicSocialDiscovery,
  publicSocialDiscoverySchema,
} from "./social-discovery";

const source = {
  id: "bluesky_jetstream",
  name: "Bluesky Jetstream discovery",
  kind: "social",
  access: "public",
  status: "operational",
  lastCollectedAt: "2026-08-30T10:45:00Z",
  url: "https://bsky.network/docs/jetstream/",
  note: "42 retained activity candidates. Bounded live coverage only; never opening evidence, geography, a hit, or a pull-rate denominator.",
} as const;

describe("public social discovery supplement", () => {
  it("accepts the exact public-safe Bluesky identity and appends it", () => {
    const payload = { schemaVersion: "1.0.0", sources: [source] };

    expect(publicSocialDiscoverySchema.parse(payload)).toEqual(payload);
    const merged = mergePublicSocialDiscovery(DEMO_PUBLIC_DATA, payload);

    expect(merged).toMatchObject({
      sources: expect.arrayContaining([source]),
    });
  });

  it("fails closed on identity drift, private fields, and source collisions", () => {
    const drifted = {
      schemaVersion: "1.0.0",
      sources: [{ ...source, url: "https://example.com/stream" }],
    };
    const privatePayload = {
      schemaVersion: "1.0.0",
      sources: [{ ...source, cursor: "123", did: "did:plc:private" }],
    };
    const collision = {
      ...DEMO_PUBLIC_DATA,
      sources: [...DEMO_PUBLIC_DATA.sources, source],
    };

    expect(mergePublicSocialDiscovery(DEMO_PUBLIC_DATA, drifted)).toBe(
      DEMO_PUBLIC_DATA,
    );
    expect(mergePublicSocialDiscovery(DEMO_PUBLIC_DATA, privatePayload)).toBe(
      DEMO_PUBLIC_DATA,
    );
    expect(
      mergePublicSocialDiscovery(collision, {
        schemaVersion: "1.0.0",
        sources: [source],
      }),
    ).toBe(collision);
  });
});
