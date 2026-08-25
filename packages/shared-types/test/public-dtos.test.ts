import { describe, expect, it } from "vitest";

import { publicOpeningObservationSchema } from "../src/index.js";

const validObservation = {
  id: "obs_demo_001",
  setCode: "DEMO-A",
  productName: "Demo Booster Bundle",
  productType: "booster_bundle",
  openedAt: "2026-01-15T12:00:00Z",
  packCount: 12,
  hitCount: 3,
  rarityCounts: {
    double_rare: 2,
    illustration_rare: 1,
  },
  countryCode: "ZZ",
  region: "Demo Region",
  evidenceTier: "A",
  status: "accepted",
  sourceKind: "fixture",
  isFixture: true,
} as const;

describe("publicOpeningObservationSchema", () => {
  it("accepts a sanitized observation with the canonical product type", () => {
    expect(publicOpeningObservationSchema.parse(validObservation)).toEqual(validObservation);
  });

  it.each([
    "sourceUrl",
    "author",
    "rawAiOutput",
    "cookie",
    "token",
    "jobPayload",
    "browserProfile",
  ])("rejects private field %s", (field) => {
    expect(
      publicOpeningObservationSchema.safeParse({
        ...validObservation,
        [field]: "private",
      }).success,
    ).toBe(false);
  });

  it("never publishes rejected observations", () => {
    expect(
      publicOpeningObservationSchema.safeParse({
        ...validObservation,
        status: "rejected",
      }).success,
    ).toBe(false);
  });

  it("rejects invalid bounds and country identifiers", () => {
    expect(
      publicOpeningObservationSchema.safeParse({ ...validObservation, packCount: 0 }).success,
    ).toBe(false);
    expect(
      publicOpeningObservationSchema.safeParse({ ...validObservation, countryCode: "USA" }).success,
    ).toBe(false);
  });

  it("requires fixture provenance to agree with the fixture marker", () => {
    expect(
      publicOpeningObservationSchema.safeParse({
        ...validObservation,
        sourceKind: "public_web",
      }).success,
    ).toBe(false);
  });
});
