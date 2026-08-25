import { describe, expect, it } from "vitest";

import {
  publicFreshnessStatusSchema,
  publicRecentActivityItemSchema,
  publicSystemStatusSchema,
} from "../src/index.js";

const activity = {
  id: "activity-demo-1",
  kind: "opening",
  subject: { kind: "set", id: "sv-demo", label: "Demo Set" },
  occurredAt: "2026-08-24T10:00:00Z",
  observedAt: "2026-08-24T10:05:00Z",
  packCount: 6,
  productType: "booster_bundle",
  evidenceTier: "A",
  status: "accepted",
  countryCode: "AU",
  statisticsEligible: true,
  region: "Australia West",
  isFixture: true,
} as const;

const freshness = {
  status: "fresh",
  asOf: "2026-08-25T03:00:00Z",
  lastSuccessfulCollectionAt: "2026-08-25T02:45:00Z",
  ageSeconds: 900,
  nextExpectedAt: "2026-08-25T04:00:00Z",
} as const;

const system = {
  status: "degraded",
  checkedAt: "2026-08-25T03:00:00Z",
  components: [
    {
      id: "ingestion",
      name: "Source ingestion",
      status: "degraded",
      checkedAt: "2026-08-25T03:00:00Z",
    },
  ],
} as const;

describe("recent public activity", () => {
  it("accepts a sanitized activity item", () => {
    expect(publicRecentActivityItemSchema.parse(activity)).toEqual(activity);
  });

  it("rejects non-Australian and incoherent statistics-eligible activity", () => {
    expect(
      publicRecentActivityItemSchema.safeParse({ ...activity, countryCode: "US" }).success,
    ).toBe(false);
    expect(
      publicRecentActivityItemSchema.safeParse({
        ...activity,
        status: "activity_only",
        statisticsEligible: true,
      }).success,
    ).toBe(false);
  });

  it("never publishes rejected evidence", () => {
    expect(
      publicRecentActivityItemSchema.safeParse({ ...activity, status: "rejected" }).success,
    ).toBe(false);
  });

  it.each(["author", "sourceUrl", "rawAiOutput", "browserProfile"])(
    "rejects the private field %s",
    (field) => {
      expect(
        publicRecentActivityItemSchema.safeParse({ ...activity, [field]: "private" }).success,
      ).toBe(false);
    },
  );
});

describe("public freshness and system status", () => {
  it("accepts coherent freshness data", () => {
    expect(publicFreshnessStatusSchema.parse(freshness)).toEqual(freshness);
  });

  it("requires unavailable freshness to omit collection timestamps", () => {
    expect(
      publicFreshnessStatusSchema.safeParse({ ...freshness, status: "unavailable" }).success,
    ).toBe(false);
    expect(
      publicFreshnessStatusSchema.parse({
        status: "unavailable",
        asOf: freshness.asOf,
        lastSuccessfulCollectionAt: null,
        ageSeconds: null,
        nextExpectedAt: null,
      }),
    ).toBeDefined();
  });

  it("accepts a bounded public component status list", () => {
    expect(publicSystemStatusSchema.parse(system)).toEqual(system);
  });

  it.each(["jobPayload", "cookie", "token", "browserProfile"])(
    "rejects internal component field %s",
    (field) => {
      const unsafe = {
        ...system,
        components: [{ ...system.components[0], [field]: "private" }],
      };
      expect(publicSystemStatusSchema.safeParse(unsafe).success).toBe(false);
    },
  );
});
