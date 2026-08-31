import { z } from "zod";

import { publicDashboardDataSchema } from "./schema";
import type { PublicDashboardData } from "./types";

const BLUESKY_SOURCE_ID = "bluesky_jetstream" as const;
const BLUESKY_SOURCE_NAME = "Bluesky Jetstream discovery" as const;
const BLUESKY_SOURCE_URL = "https://bsky.network/docs/jetstream/" as const;

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

export const publicSocialDiscoverySchema = z
  .object({
    schemaVersion: z.literal("1.0.0"),
    sources: z.tuple([blueskySource]),
  })
  .strict();

export function mergePublicSocialDiscovery(
  snapshot: unknown,
  discoveryPayload: unknown,
): unknown {
  const snapshotResult = publicDashboardDataSchema.safeParse(snapshot);
  const discoveryResult = publicSocialDiscoverySchema.safeParse(discoveryPayload);
  if (!snapshotResult.success || !discoveryResult.success) return snapshot;

  const base = snapshotResult.data;
  const discovery = discoveryResult.data;
  const baseSourceIds = new Set(base.sources.map((source) => source.id));
  if (discovery.sources.some((source) => baseSourceIds.has(source.id))) return snapshot;

  return {
    ...base,
    sources: [...base.sources, ...discovery.sources],
  } satisfies PublicDashboardData;
}
