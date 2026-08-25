import { describe, expect, it } from "vitest";

import {
  publicBatchSummarySchema,
  publicRegionSummarySchema,
  publicRetailerSummarySchema,
  publicSetSummarySchema,
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

describe("public aggregate summaries", () => {
  it("accepts bounded set summaries", () => {
    expect(publicSetSummarySchema.parse(setSummary)).toEqual(setSummary);
  });

  it("accepts bounded region summaries", () => {
    expect(publicRegionSummarySchema.parse(regionSummary)).toEqual(regionSummary);
  });

  it("accepts bounded retailer summaries", () => {
    expect(publicRetailerSummarySchema.parse(retailerSummary)).toEqual(retailerSummary);
  });

  it("accepts bounded batch summaries", () => {
    expect(publicBatchSummarySchema.parse(batchSummary)).toEqual(batchSummary);
  });

  it.each([
    [publicSetSummarySchema, setSummary],
    [publicRegionSummarySchema, regionSummary],
    [publicRetailerSummarySchema, retailerSummary],
    [publicBatchSummarySchema, batchSummary],
  ])("rejects private fields for every summary schema", (schema, value) => {
    expect(schema.safeParse({ ...value, sourceUrl: "https://private.invalid/item" }).success).toBe(false);
    expect(schema.safeParse({ ...value, author: "personal-handle" }).success).toBe(false);
  });

  it("keeps the observed rate distinct from the posterior interval", () => {
    expect(
      publicSetSummarySchema.safeParse({
        ...setSummary,
        independentSources: 3,
        baselineRate: 0.14,
        posteriorMean: 0.15,
        hitRate: 0.5,
        deltaFromBaseline: 0.36,
      }).success,
    ).toBe(true);
  });

  it("requires source, baseline, and posterior audit context", () => {
    const complete = {
      ...setSummary,
      independentSources: 3,
      baselineRate: 0.14,
      posteriorMean: 0.15,
    };
    for (const field of ["independentSources", "baselineRate", "posteriorMean"] as const) {
      const candidate: Record<string, unknown> = { ...complete };
      delete candidate[field];
      expect(publicSetSummarySchema.safeParse(candidate).success).toBe(false);
    }
  });

  it("rejects independent-source counts above complete openings", () => {
    expect(
      publicSetSummarySchema.safeParse({
        ...setSummary,
        independentSources: setSummary.openings + 1,
      }).success,
    ).toBe(false);
  });

  it("rejects incoherent rates and intervals", () => {
    expect(
      publicSetSummarySchema.safeParse({
        ...setSummary,
        credibleInterval: { low: 0.16, high: 0.2, level: 0.9 },
      }).success,
    ).toBe(false);
    expect(
      publicSetSummarySchema.safeParse({
        ...setSummary,
        hitRate: null,
      }).success,
    ).toBe(false);
    expect(
      publicSetSummarySchema.safeParse({
        ...setSummary,
        signalLabel: "Insufficient sample",
      }).success,
    ).toBe(false);
  });

  it("requires the published delta to match observed rate minus baseline", () => {
    expect(
      publicSetSummarySchema.safeParse({ ...setSummary, deltaFromBaseline: null }).success,
    ).toBe(false);
    expect(
      publicSetSummarySchema.safeParse({ ...setSummary, deltaFromBaseline: 0.5 }).success,
    ).toBe(false);
  });

  it("withholds the baseline together with all tiny-sample rate estimates", () => {
    expect(
      publicSetSummarySchema.safeParse({
        ...setSummary,
        packsObserved: 29,
        openings: 2,
        independentSources: 2,
        baselineRate: null,
        hitRate: null,
        posteriorMean: null,
        credibleInterval: null,
        deltaFromBaseline: null,
        signalLabel: "Insufficient sample",
      }).success,
    ).toBe(true);
  });

  it("withholds all inference below three independent sources", () => {
    expect(
      publicSetSummarySchema.safeParse({
        ...setSummary,
        independentSources: 2,
      }).success,
    ).toBe(false);
    expect(
      publicSetSummarySchema.safeParse({
        ...setSummary,
        independentSources: 2,
        baselineRate: null,
        hitRate: null,
        posteriorMean: null,
        credibleInterval: null,
        deltaFromBaseline: null,
        signalLabel: "Insufficient sample",
      }).success,
    ).toBe(true);
  });

  it("requires a posterior mean whenever the observed rate is published", () => {
    expect(
      publicSetSummarySchema.safeParse({ ...setSummary, posteriorMean: null }).success,
    ).toBe(false);
  });

  it("withholds the posterior mean whenever the observed rate is withheld", () => {
    expect(
      publicSetSummarySchema.safeParse({
        ...setSummary,
        packsObserved: 29,
        hitRate: null,
        posteriorMean: 0.15,
        credibleInterval: null,
        deltaFromBaseline: null,
        signalLabel: "Insufficient sample",
      }).success,
    ).toBe(false);
  });

  it("enforces Australia-only scope and conservative signal sample gates", () => {
    expect(
      publicRegionSummarySchema.safeParse({ ...regionSummary, countryCode: "US" }).success,
    ).toBe(false);
    expect(
      publicSetSummarySchema.safeParse({
        ...setSummary,
        packsObserved: 199,
        signalLabel: "Possible anomaly",
      }).success,
    ).toBe(false);
    expect(
      publicSetSummarySchema.safeParse({
        ...setSummary,
        packsObserved: 30,
        hitRate: null,
        credibleInterval: null,
        deltaFromBaseline: null,
        signalLabel: "Insufficient sample",
      }).success,
    ).toBe(false);
  });

  it("rejects impossible calendar dates without throwing", () => {
    expect(() =>
      publicSetSummarySchema.safeParse({ ...setSummary, releaseDate: "2026-99-99" }),
    ).not.toThrow();
    expect(
      publicSetSummarySchema.safeParse({ ...setSummary, releaseDate: "2026-99-99" }).success,
    ).toBe(false);
  });

  it("rejects reversed batch observation dates", () => {
    expect(
      publicBatchSummarySchema.safeParse({
        ...batchSummary,
        firstObservedAt: "2026-08-25T10:00:00Z",
      }).success,
    ).toBe(false);
  });
});
