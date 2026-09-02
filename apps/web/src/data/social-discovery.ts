import { z } from "zod";

import {
  publicDashboardDataSchema,
  publicSocialDiscoveryV4Schema as publicSocialDiscoveryV4Contract,
} from "./schema";
import type { PublicDashboardData } from "./types";

const BLUESKY_SOURCE_ID = "bluesky_jetstream" as const;
const BLUESKY_SOURCE_NAME = "Bluesky Jetstream discovery" as const;
const BLUESKY_SOURCE_URL = "https://bsky.network/docs/jetstream/" as const;
const NOSTR_SOURCE_ID = "nostr_multi_relay" as const;
const NOSTR_SOURCE_NAME = "Nostr multi-relay discovery" as const;
const NOSTR_SOURCE_URL =
  "https://github.com/nostr-protocol/nips/blob/master/01.md" as const;
const MASTODON_SOURCE_ID = "mastodon_public_hashtag" as const;
const MASTODON_SOURCE_NAME = "Mastodon public hashtag discovery" as const;
const MASTODON_SOURCE_URL =
  "https://docs.joinmastodon.org/methods/timelines/" as const;

const isoDateTime = z.string().datetime({ offset: true });

const blueskySource = z
  .object({
    id: z.literal(BLUESKY_SOURCE_ID),
    name: z.literal(BLUESKY_SOURCE_NAME),
    kind: z.literal("social"),
    access: z.literal("public"),
    status: z.enum(["operational", "delayed", "attention", "paused"]),
    lastCollectedAt: isoDateTime.nullable(),
    url: z.literal(BLUESKY_SOURCE_URL),
    note: z.string().min(1).max(500),
  })
  .strict();

const nostrSource = z
  .object({
    id: z.literal(NOSTR_SOURCE_ID),
    name: z.literal(NOSTR_SOURCE_NAME),
    kind: z.literal("social"),
    access: z.literal("public"),
    status: z.enum(["operational", "delayed", "attention", "paused"]),
    lastCollectedAt: isoDateTime.nullable(),
    url: z.literal(NOSTR_SOURCE_URL),
    note: z.string().min(1).max(500),
  })
  .strict();

const mastodonSource = z
  .object({
    id: z.literal(MASTODON_SOURCE_ID),
    name: z.literal(MASTODON_SOURCE_NAME),
    kind: z.literal("social"),
    access: z.literal("public"),
    status: z.enum(["operational", "delayed", "attention", "paused"]),
    lastCollectedAt: isoDateTime.nullable(),
    url: z.literal(MASTODON_SOURCE_URL),
    note: z.string().min(1).max(500),
  })
  .strict();

export const publicSocialDiscoveryV1Schema = z
  .object({
    schemaVersion: z.literal("1.0.0"),
    sources: z.tuple([blueskySource]),
  })
  .strict();

export const publicSocialDiscoveryV2Schema = z
  .object({
    schemaVersion: z.literal("2.0.0"),
    sources: z.tuple([blueskySource, nostrSource]),
  })
  .strict();

export const publicSocialDiscoveryV3Schema = z
  .object({
    schemaVersion: z.literal("3.0.0"),
    sources: z.tuple([blueskySource, nostrSource, mastodonSource]),
  })
  .strict();

// V4 is a deliberately separate activity pulse. It does not append source
// cards to the dashboard's provenance list because its DTO has no URLs,
// notes, or other evidence-facing fields. The only retained values are
// bounded per-platform counts and collection freshness.
export const publicSocialDiscoveryV4Schema = publicSocialDiscoveryV4Contract;

// The v4 activity pulse is the current contract. V1-v3 remain read-only
// compatibility paths for installations that have not yet applied the latest
// projection; only v4 creates the dedicated pulse field below.
export const publicSocialDiscoverySchema = publicSocialDiscoveryV4Schema;

export function mergePublicSocialDiscovery(
  snapshot: unknown,
  discoveryPayload: unknown,
): unknown {
  const snapshotResult = publicDashboardDataSchema.safeParse(snapshot);
  const v4Result = publicSocialDiscoveryV4Schema.safeParse(discoveryPayload);
  if (snapshotResult.success && v4Result.success) {
    const candidate = {
      ...snapshotResult.data,
      socialActivityPulse: v4Result.data,
    } satisfies PublicDashboardData;
    const merged = publicDashboardDataSchema.safeParse(candidate);
    return merged.success ? merged.data : snapshot;
  }

  const v3Result = publicSocialDiscoveryV3Schema.safeParse(discoveryPayload);
  const discoveryResult = v3Result.success
    ? v3Result
    : publicSocialDiscoveryV1Schema.safeParse(discoveryPayload);
  if (!snapshotResult.success || !discoveryResult.success) return snapshot;

  const base = snapshotResult.data;
  const discovery = discoveryResult.data;
  const discoveryById = new Map(discovery.sources.map((source) => [source.id, source]));
  const baseSourceIds = new Set(base.sources.map((source) => source.id));
  const mergedSources = base.sources.map(
    (source) => discoveryById.get(source.id) ?? source,
  );
  mergedSources.push(
    ...discovery.sources.filter((source) => !baseSourceIds.has(source.id)),
  );

  const candidate = {
    ...base,
    sources: mergedSources,
  } satisfies PublicDashboardData;
  const merged = publicDashboardDataSchema.safeParse(candidate);
  return merged.success ? merged.data : snapshot;
}
