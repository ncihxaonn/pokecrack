import { describe, expect, it } from "vitest";

import {
  PUBLIC_PAYLOAD_SCHEMA_VERSION,
  cursorPaginationSchema,
  offsetPaginationSchema,
  publicCompactDashboardPayloadSchema,
  publicSetPageSchema,
} from "../src/index.js";

const setSummary = {
  id: "sv-demo",
  slug: "demo-set",
  name: "Demo Set",
  series: "Demo Series",
  releaseDate: "2026-01-15",
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

const overview = {
  schemaVersion: PUBLIC_PAYLOAD_SCHEMA_VERSION,
  mode: "demo",
  generatedAt: "2026-08-25T03:00:00Z",
  summary: {
    packsObserved: 120,
    openings: 20,
    verifiedSources: 3,
    coverageDays: 7,
    baselineHitRate: 0.15,
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

const compactPayload = {
  overview,
  sets: [setSummary],
  regions: [],
  retailers: [],
  batches: [],
  recentActivity: [],
  signals: [],
} as const;

describe("pagination contracts", () => {
  it("accepts coherent opaque cursor metadata", () => {
    const page = { limit: 25, nextCursor: "cursor_demo_2", hasMore: true } as const;
    expect(cursorPaginationSchema.parse(page)).toEqual(page);
  });

  it("requires hasMore and nextCursor to agree", () => {
    expect(
      cursorPaginationSchema.safeParse({ limit: 25, nextCursor: null, hasMore: true }).success,
    ).toBe(false);
    expect(
      cursorPaginationSchema.safeParse({ limit: 25, nextCursor: "cursor", hasMore: false }).success,
    ).toBe(false);
  });

  it("validates offset totals and navigation flags", () => {
    const page = {
      page: 3,
      pageSize: 100,
      totalItems: 201,
      totalPages: 3,
      hasNextPage: false,
      hasPreviousPage: true,
    } as const;
    expect(offsetPaginationSchema.parse(page)).toEqual(page);
    expect(
      offsetPaginationSchema.safeParse({ ...page, totalPages: 2 }).success,
    ).toBe(false);
    expect(
      offsetPaginationSchema.safeParse({
        page: 2,
        pageSize: 25,
        totalItems: 0,
        totalPages: 0,
        hasNextPage: false,
        hasPreviousPage: false,
      }).success,
    ).toBe(false);
  });

  it("provides strict concrete pages for public summaries", () => {
    const page = {
      items: [setSummary],
      pagination: { limit: 25, nextCursor: null, hasMore: false },
    } as const;
    expect(publicSetPageSchema.parse(page)).toEqual(page);
    expect(publicSetPageSchema.safeParse({ ...page, jobPayload: {} }).success).toBe(false);
    expect(
      publicSetPageSchema.safeParse({
        items: [setSummary, setSummary],
        pagination: { limit: 1, nextCursor: null, hasMore: false },
      }).success,
    ).toBe(false);
  });
});

describe("compact dashboard payload", () => {
  it("accepts only bounded public summary data", () => {
    expect(publicCompactDashboardPayloadSchema.parse(compactPayload)).toEqual(compactPayload);
  });

  it.each([
    "admin",
    "jobs",
    "cookies",
    "tokens",
    "browserProfiles",
    "rawAiOutput",
    "authors",
    "brand",
    "disclaimer",
  ])("rejects non-public compact field %s", (field) => {
    expect(
      publicCompactDashboardPayloadSchema.safeParse({
        ...compactPayload,
        [field]: [],
      }).success,
    ).toBe(false);
  });

  it("rejects oversized compact collections", () => {
    expect(
      publicCompactDashboardPayloadSchema.safeParse({
        ...compactPayload,
        sets: Array.from({ length: 51 }, (_, index) => ({
          ...setSummary,
          id: `set-${index}`,
          slug: `set-${index}`,
        })),
      }).success,
    ).toBe(false);
  });
});
