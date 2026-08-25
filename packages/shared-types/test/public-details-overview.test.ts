import { describe, expect, it } from "vitest";

import {
  PUBLIC_PAYLOAD_SCHEMA_VERSION,
  publicBatchDetailSchema,
  publicDashboardOverviewSchema,
  publicRegionDetailSchema,
  publicRetailerDetailSchema,
  publicSetDetailSchema,
  publicTrendPointSchema,
} from "../src/index.js";

const metric = {
  packsObserved: 120,
  openings: 20,
  independentSources: 3,
  baselineRate: 0.14,
  hitRate: 0.15,
  posteriorMean: 0.15,
  credibleInterval: { low: 0.1, high: 0.2, level: 0.9 },
  deltaFromBaseline: 0.01,
  signalLabel: "No significant signal",
  updatedAt: "2026-08-25T03:00:00Z",
  isFixture: true,
} as const;

const setSummary = {
  id: "sv-demo",
  slug: "demo-set",
  name: "Demo Set",
  series: "Demo Series",
  releaseDate: "2026-01-15",
  ...metric,
} as const;

const regionSummary = {
  id: "region-us-west",
  slug: "us-west",
  name: "Australia West",
  countryCode: "AU",
  coverage: "State-level aggregate",
  ...metric,
} as const;

const retailerSummary = {
  id: "retailer-demo",
  slug: "retailer-demo",
  name: "Illustrative retailer",
  region: "Australia West",
  channel: "specialty",
  ...metric,
} as const;

const batchSummary = {
  id: "batch-demo",
  code: "DEMO-2409-A",
  setId: "sv-demo",
  setName: "Demo Set",
  region: "Australia West",
  firstObservedAt: "2026-08-01T10:00:00Z",
  lastObservedAt: "2026-08-24T10:00:00Z",
  ...metric,
} as const;

const sections = {
  trend: [],
  signals: [],
  recentActivity: [],
} as const;

const details = [
  [publicSetDetailSchema, { summary: setSummary, products: [], ...sections }],
  [publicRegionDetailSchema, { summary: regionSummary, sets: [], ...sections }],
  [publicRetailerDetailSchema, { summary: retailerSummary, sets: [], ...sections }],
  [publicBatchDetailSchema, { summary: batchSummary, products: [], ...sections }],
] as const;

const overview = {
  schemaVersion: PUBLIC_PAYLOAD_SCHEMA_VERSION,
  mode: "demo",
  generatedAt: "2026-08-25T03:00:00Z",
  summary: {
    packsObserved: 4_872,
    openings: 621,
    verifiedSources: 14,
    coverageDays: 90,
    baselineHitRate: 0.142,
  },
  freshness: {
    status: "fresh",
    asOf: "2026-08-25T03:00:00Z",
    lastSuccessfulCollectionAt: "2026-08-25T02:45:00Z",
    ageSeconds: 900,
    nextExpectedAt: "2026-08-25T04:00:00Z",
  },
  system: {
    status: "operational",
    checkedAt: "2026-08-25T03:00:00Z",
    components: [],
  },
} as const;

describe("public detail DTOs", () => {
  it.each(details)("accepts a bounded detail document", (schema, value) => {
    expect(schema.parse(value)).toEqual(value);
  });

  it.each(details)("rejects internal detail fields", (schema, value) => {
    expect(schema.safeParse({ ...value, rawObservations: [] }).success).toBe(false);
    expect(schema.safeParse({ ...value, authorProfiles: [] }).success).toBe(false);
  });
});

describe("public trend point", () => {
  const insufficient = {
    date: "2026-08-25",
    packsObserved: 29,
    completeOpenings: 2,
    independentSources: 2,
    observedRate: null,
    baselineRate: null,
  } as const;

  it("withholds inference below pack or independent-source minimums", () => {
    expect(publicTrendPointSchema.safeParse(insufficient).success).toBe(true);
    expect(
      publicTrendPointSchema.safeParse({
        ...insufficient,
        observedRate: 0.5,
        baselineRate: 0.4,
      }).success,
    ).toBe(false);
    expect(
      publicTrendPointSchema.safeParse({
        ...insufficient,
        packsObserved: 30,
        completeOpenings: 3,
        independentSources: 3,
        observedRate: 0.5,
        baselineRate: 0.4,
      }).success,
    ).toBe(true);
  });
});

describe("dashboard overview", () => {
  it("accepts a versioned public overview", () => {
    expect(publicDashboardOverviewSchema.parse(overview)).toEqual(overview);
  });

  it.each(["admin", "jobs", "browserSessions", "aiUsage", "brandName"])(
    "rejects non-public overview field %s",
    (field) => {
      expect(
        publicDashboardOverviewSchema.safeParse({ ...overview, [field]: [] }).success,
      ).toBe(false);
    },
  );

  it("withholds the dashboard baseline below pack or source minimums", () => {
    const insufficient = {
      ...overview,
      summary: {
        ...overview.summary,
        packsObserved: 29,
        openings: 2,
        verifiedSources: 2,
        baselineHitRate: null,
      },
    };

    expect(publicDashboardOverviewSchema.safeParse(insufficient).success).toBe(true);
    expect(
      publicDashboardOverviewSchema.safeParse({
        ...insufficient,
        summary: { ...insufficient.summary, baselineHitRate: 0.5 },
      }).success,
    ).toBe(false);
  });

  it("rejects incoherent overview totals", () => {
    expect(
      publicDashboardOverviewSchema.safeParse({
        ...overview,
        summary: { ...overview.summary, openings: 5_000 },
      }).success,
    ).toBe(false);
    expect(
      publicDashboardOverviewSchema.safeParse({
        ...overview,
        summary: {
          ...overview.summary,
          openings: 1,
          verifiedSources: 3,
        },
      }).success,
    ).toBe(false);
  });
});
