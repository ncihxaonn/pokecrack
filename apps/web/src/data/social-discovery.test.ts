import { describe, expect, it } from "vitest";

import { DEMO_PUBLIC_DATA } from "./demo";
import {
  mergePublicSocialDiscovery,
  publicSocialDiscoverySchema,
  publicSocialDiscoveryV1Schema,
  publicSocialDiscoveryV2Schema,
  publicSocialDiscoveryV3Schema,
  publicSocialDiscoveryV4Schema,
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

const validV3Payload = {
  schemaVersion: "3.0.0",
  sources: [blueskySource, nostrSource, mastodonSource],
} as const;

const pulseBlueskySource = {
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
} as const;
const pulseNostrSource = {
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
} as const;
const pulseMastodonSource = {
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
} as const;
const validV4Payload = {
  schemaVersion: "4.0.0",
  window: {
    start: "2026-08-30T10:45:00Z",
    end: "2026-08-31T10:45:00Z",
  },
  activityOnly: true,
  nonEvidence: true,
  sources: [pulseBlueskySource, pulseNostrSource, pulseMastodonSource],
} as const;

describe("public social discovery supplement", () => {
  it("accepts and merges the strict v4 activity pulse without changing provenance cards", () => {
    expect(publicSocialDiscoverySchema.parse(validV4Payload)).toEqual(validV4Payload);
    const merged = mergePublicSocialDiscovery(DEMO_PUBLIC_DATA, validV4Payload) as typeof DEMO_PUBLIC_DATA;

    expect(merged.sources).toEqual(DEMO_PUBLIC_DATA.sources);
    expect(merged.socialActivityPulse).toEqual(validV4Payload);
  });

  it("accepts every legacy source status while rejecting unavailable", () => {
    for (const status of ["operational", "delayed", "attention", "paused"] as const) {
      expect(
        publicSocialDiscoveryV3Schema.safeParse({
          ...validV3Payload,
          sources: [blueskySource, nostrSource, { ...mastodonSource, status }],
        }).success,
      ).toBe(true);
    }
    expect(
      publicSocialDiscoveryV3Schema.safeParse({
        ...validV3Payload,
        sources: [
          blueskySource,
          nostrSource,
          { ...mastodonSource, status: "unavailable" },
        ],
      }).success,
    ).toBe(false);
  });

  it("rejects the old two-source v2 payload and every source-order drift", () => {
    const oldV2Payload = {
      schemaVersion: "2.0.0",
      sources: [blueskySource, nostrSource],
    };
    const wrongOrderPayload = {
      schemaVersion: "3.0.0",
      sources: [nostrSource, blueskySource, mastodonSource],
    };

    expect(publicSocialDiscoverySchema.safeParse(oldV2Payload).success).toBe(false);
    expect(publicSocialDiscoveryV2Schema.parse(oldV2Payload)).toEqual(oldV2Payload);
    expect(publicSocialDiscoveryV3Schema.safeParse(wrongOrderPayload).success).toBe(false);
    expect(mergePublicSocialDiscovery(DEMO_PUBLIC_DATA, oldV2Payload)).toBe(
      DEMO_PUBLIC_DATA,
    );
    expect(mergePublicSocialDiscovery(DEMO_PUBLIC_DATA, wrongOrderPayload)).toBe(
      DEMO_PUBLIC_DATA,
    );
  });

  it("accepts the v1 Bluesky-only tuple without inventing a Nostr source", () => {
    const payload = {
      schemaVersion: "1.0.0",
      sources: [blueskySource],
    };

    expect(publicSocialDiscoveryV1Schema.parse(payload)).toEqual(payload);
    expect(() =>
      publicSocialDiscoveryV1Schema.parse({
        schemaVersion: "1.0.0",
        sources: [blueskySource, nostrSource],
      }),
    ).toThrow();

    const merged = mergePublicSocialDiscovery(DEMO_PUBLIC_DATA, payload);
    expect(merged).toMatchObject({ sources: expect.arrayContaining([blueskySource]) });
    expect((merged as typeof DEMO_PUBLIC_DATA).sources).not.toEqual(
      expect.arrayContaining([nostrSource]),
    );
  });

  it("fails closed on identity drift, private fields, and source collisions", () => {
    const drifted = {
      ...validV3Payload,
      sources: [
        blueskySource,
        nostrSource,
        { ...mastodonSource, url: "https://mastodon.social/tags/pokemon" },
      ],
    };
    const privatePayloads = [
      "instance",
      "statusId",
      "handle",
      "content",
      "urlHash",
      "cursor",
      "rateLimitHeaders",
      "rawError",
    ] as const;
    const collision = {
      ...DEMO_PUBLIC_DATA,
      sources: [...DEMO_PUBLIC_DATA.sources, mastodonSource],
    };

    expect(publicSocialDiscoveryV3Schema.safeParse(drifted).success).toBe(false);
    expect(mergePublicSocialDiscovery(DEMO_PUBLIC_DATA, drifted)).toBe(
      DEMO_PUBLIC_DATA,
    );
    for (const field of privatePayloads) {
      const privatePayload = {
        ...validV3Payload,
        sources: [
          blueskySource,
          nostrSource,
          { ...mastodonSource, [field]: "private" },
        ],
      };
      expect(publicSocialDiscoveryV3Schema.safeParse(privatePayload).success).toBe(false);
      expect(mergePublicSocialDiscovery(DEMO_PUBLIC_DATA, privatePayload)).toBe(
        DEMO_PUBLIC_DATA,
      );
    }
    expect(
      mergePublicSocialDiscovery(collision, {
        schemaVersion: "3.0.0",
        sources: [blueskySource, nostrSource, mastodonSource],
      }),
    ).toBe(collision);
  });

  it("rejects v4 fields that could become evidence, identity, or provider payload", () => {
    for (const field of [
      "text",
      "url",
      "uri",
      "eventId",
      "statusId",
      "hash",
      "author",
      "tag",
      "cursor",
      "rawPayload",
      "country",
      "pack",
      "rate",
    ] as const) {
      const payload = {
        ...validV4Payload,
        sources: [
          { ...pulseBlueskySource, [field]: "private" },
          pulseNostrSource,
          pulseMastodonSource,
        ],
      };
      expect(publicSocialDiscoveryV4Schema.safeParse(payload).success).toBe(false);
      expect(mergePublicSocialDiscovery(DEMO_PUBLIC_DATA, payload)).toBe(DEMO_PUBLIC_DATA);
    }
    expect(
      publicSocialDiscoveryV4Schema.safeParse({
        ...validV4Payload,
        window: { start: "2026-08-30T10:45:00Z", end: "2026-08-31T09:45:00Z" },
      }).success,
    ).toBe(false);
    expect(
      publicSocialDiscoveryV4Schema.safeParse({
        ...validV4Payload,
        sources: [
          { ...pulseBlueskySource, status: "delayed", freshness: "fresh" },
          pulseNostrSource,
          pulseMastodonSource,
        ],
      }).success,
    ).toBe(false);
  });
});
