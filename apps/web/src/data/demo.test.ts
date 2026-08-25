import { describe, expect, it } from "vitest";

import { DEMO_DATA } from "./demo";
import { publicDashboardDataSchema } from "./schema";

describe("DEMO_DATA", () => {
  it("contains deterministic dashboard coverage and all required evidence states", () => {
    expect(DEMO_DATA.mode).toBe("demo");
    expect(DEMO_DATA.summary.observedPacks).toBeGreaterThan(1_000);
    expect(DEMO_DATA.summary.completeOpenings).toBeGreaterThan(0);
    expect(DEMO_DATA.summary.aiValidatedSources).toBeGreaterThan(0);
    expect(DEMO_DATA.summary.trackedSets).toBe(DEMO_DATA.sets.length);
    expect(DEMO_DATA.summary.trackedRegions).toBe(DEMO_DATA.regions.length);
    expect(DEMO_DATA.summary.batchSightings).toBe(DEMO_DATA.batches.length);
    expect(DEMO_DATA.summary.australiaCoverage).toMatch(/Australia/i);
    expect(DEMO_DATA.summary.methodologyVersion).toMatch(/^v\d/);
    expect(DEMO_DATA.sets.some((item) => item.state === "anomaly")).toBe(true);
    expect(DEMO_DATA.sets.some((item) => item.state === "watch")).toBe(true);
    expect(DEMO_DATA.sets.some((item) => item.state === "insufficient")).toBe(true);
    expect(DEMO_DATA.regions.map((item) => item.state)).not.toContain("activity-only");
    expect(
      DEMO_DATA.sources.some((item) => item.access === "browser-auth-required"),
    ).toBe(true);
    expect(DEMO_DATA.recentActivity.length).toBeGreaterThan(2);
    expect(
      DEMO_DATA.recentActivity.some((item) => item.classification === "activity-only"),
    ).toBe(true);
    expect(
      DEMO_DATA.recentActivity
        .filter((item) => item.classification === "activity-only")
        .every((item) => item.statisticsEligible === false),
    ).toBe(true);
  });

  it("keeps demo scope Australia-only and limited to supported physical products", () => {
    expect(DEMO_DATA.regions.every((item) => item.countryCode === "AU")).toBe(true);
    expect(
      DEMO_DATA.regions.every((item) =>
        /Australia|Sydney|Melbourne|Brisbane|Adelaide|Perth|Hobart|Darwin|Canberra/.test(
          `${item.name} ${item.coverage}`,
        ),
      ),
    ).toBe(true);
    expect(new Set(DEMO_DATA.batches.map((item) => item.productType))).toEqual(
      new Set(["Booster Box", "ETB", "Booster Bundle"]),
    );
    expect(DEMO_DATA.admin.browserSessions.map((item) => item.profile)).toEqual([
      "social-western",
      "social-chinese",
      "research-general",
    ]);
    expect(
      DEMO_DATA.admin.aiUsage.every(
        (item) => "estimatedAud" in item && !("estimatedUsd" in item),
      ),
    ).toBe(true);
  });

  it("keeps signal labels inside the conservative sample gates", () => {
    const metrics = [
      ...DEMO_DATA.sets,
      ...DEMO_DATA.regions,
      ...DEMO_DATA.retailers,
      ...DEMO_DATA.batches,
    ];
    for (const metric of metrics) {
      expect(metric.state === "insufficient").toBe(
        metric.packsObserved < 30 || metric.independentSources < 3,
      );
      if (metric.state === "watch" || metric.state === "anomaly") {
        expect(metric.packsObserved).toBeGreaterThanOrEqual(200);
      }
    }
  });

  it("rejects public snapshots that violate sample-state publication gates", () => {
    const { admin, ...publicData } = DEMO_DATA;
    expect(admin).toBeDefined();
    const invalid = {
      ...publicData,
      sets: publicData.sets.map((item, index) =>
        index === 0
          ? { ...item, packsObserved: 199, state: "anomaly" as const }
          : item,
      ),
    };
    expect(publicDashboardDataSchema.safeParse(invalid).success).toBe(false);
    const nonAustralian = {
      ...publicData,
      regions: publicData.regions.map((item, index) =>
        index === 0 ? { ...item, countryCode: "US" } : item,
      ),
    };
    expect(publicDashboardDataSchema.safeParse(nonAustralian).success).toBe(false);
  });

  it("rejects independent-source counts above complete openings", () => {
    const { admin, ...publicData } = DEMO_DATA;
    expect(admin).toBeDefined();
    const invalid = {
      ...publicData,
      sets: publicData.sets.map((item, index) =>
        index === 0
          ? { ...item, independentSources: item.openings + 1 }
          : item,
      ),
    };

    expect(publicDashboardDataSchema.safeParse(invalid).success).toBe(false);
  });

  it("rejects dashboard source totals above complete openings", () => {
    const { admin, ...publicData } = DEMO_DATA;
    expect(admin).toBeDefined();
    const invalid = {
      ...publicData,
      summary: {
        ...publicData.summary,
        completeOpenings: 1,
        aiValidatedSources: 3,
      },
    };

    expect(publicDashboardDataSchema.safeParse(invalid).success).toBe(false);
  });

  it("rejects dashboard opening totals above observed packs", () => {
    const { admin, ...publicData } = DEMO_DATA;
    expect(admin).toBeDefined();
    const invalid = {
      ...publicData,
      summary: {
        ...publicData.summary,
        completeOpenings: publicData.summary.observedPacks + 1,
      },
    };

    expect(publicDashboardDataSchema.safeParse(invalid).success).toBe(false);
  });

  it("withholds all inference below three independent sources", () => {
    const { admin, ...publicData } = DEMO_DATA;
    expect(admin).toBeDefined();
    const published = {
      ...publicData,
      sets: publicData.sets.map((item, index) =>
        index === 0 ? { ...item, independentSources: 2 } : item,
      ),
    };
    expect(publicDashboardDataSchema.safeParse(published).success).toBe(false);

    const withheld = {
      ...publicData,
      sets: publicData.sets.map((item, index) =>
        index === 0
          ? {
              ...item,
              independentSources: 2,
              baselineRate: null,
              hitRate: null,
              posteriorMean: null,
              credibleInterval: null,
              deltaFromBaseline: null,
              state: "insufficient" as const,
            }
          : item,
      ),
    };
    expect(publicDashboardDataSchema.safeParse(withheld).success).toBe(true);
  });

  it("rejects a posterior mean when the observed rate is withheld", () => {
    const { admin, ...publicData } = DEMO_DATA;
    expect(admin).toBeDefined();
    const invalid = {
      ...publicData,
      sets: publicData.sets.map((item, index) =>
        index === 3 ? { ...item, posteriorMean: 0.142 } : item,
      ),
    };

    expect(publicDashboardDataSchema.safeParse(invalid).success).toBe(false);
  });

  it("requires a posterior mean for every published observed rate", () => {
    const { admin, ...publicData } = DEMO_DATA;
    expect(admin).toBeDefined();
    const invalid = {
      ...publicData,
      sets: publicData.sets.map((item, index) =>
        index === 0 ? { ...item, posteriorMean: null } : item,
      ),
    };

    expect(publicDashboardDataSchema.safeParse(invalid).success).toBe(false);
  });

  it("rejects a posterior mean outside its credible interval", () => {
    const { admin, ...publicData } = DEMO_DATA;
    expect(admin).toBeDefined();
    const invalid = {
      ...publicData,
      sets: publicData.sets.map((item, index) =>
        index === 0 ? { ...item, posteriorMean: 0.9 } : item,
      ),
    };

    expect(publicDashboardDataSchema.safeParse(invalid).success).toBe(false);
  });

  it("rejects a published delta that contradicts the observed baseline", () => {
    const { admin, ...publicData } = DEMO_DATA;
    expect(admin).toBeDefined();
    const invalid = {
      ...publicData,
      sets: publicData.sets.map((item, index) =>
        index === 0 ? { ...item, deltaFromBaseline: null } : item,
      ),
    };

    expect(publicDashboardDataSchema.safeParse(invalid).success).toBe(false);
  });

  it("withholds the dashboard baseline until pack and source minimums are met", () => {
    const { admin, ...publicData } = DEMO_DATA;
    expect(admin).toBeDefined();
    const insufficient = {
      ...publicData,
      summary: {
        ...publicData.summary,
        observedPacks: 29,
        completeOpenings: 2,
        aiValidatedSources: 2,
        baselineHitRate: null,
      },
    };

    expect(publicDashboardDataSchema.safeParse(insufficient).success).toBe(true);
    expect(
      publicDashboardDataSchema.safeParse({
        ...insufficient,
        summary: { ...insufficient.summary, baselineHitRate: 0.5 },
      }).success,
    ).toBe(false);
  });

  it("accepts a withheld baseline for an insufficient sample", () => {
    const { admin, ...publicData } = DEMO_DATA;
    expect(admin).toBeDefined();
    const candidate = {
      ...publicData,
      sets: publicData.sets.map((item, index) =>
        index === 3 ? { ...item, baselineRate: null } : item,
      ),
    };

    expect(publicDashboardDataSchema.safeParse(candidate).success).toBe(true);
  });

  it("uses unique public identifiers", () => {
    const slugs = [
      ...DEMO_DATA.sets.map((item) => `set:${item.slug}`),
      ...DEMO_DATA.regions.map((item) => `region:${item.slug}`),
      ...DEMO_DATA.retailers.map((item) => `retailer:${item.slug}`),
      ...DEMO_DATA.batches.map((item) => `batch:${item.code}`),
    ];

    expect(new Set(slugs).size).toBe(slugs.length);
  });

  it("does not label any observed entity as lucky, hot, best, or guaranteed", () => {
    const fixtureCopy = JSON.stringify(DEMO_DATA).toLowerCase();
    expect(fixtureCopy).not.toMatch(/lucky|guaranteed|best store|hot pack/);
  });

  it("withholds trend inference below pack or independent-source minimums", () => {
    const { admin, ...publicData } = DEMO_DATA;
    expect(admin).toBeDefined();
    const insufficientTrend = {
      date: "2026-08-25",
      packsObserved: 29,
      completeOpenings: 2,
      independentSources: 2,
      observedRate: null,
      baselineRate: null,
    };

    expect(
      publicDashboardDataSchema.safeParse({
        ...publicData,
        trend: [insufficientTrend],
      }).success,
    ).toBe(true);
    expect(
      publicDashboardDataSchema.safeParse({
        ...publicData,
        trend: [{ ...insufficientTrend, observedRate: 0.5, baselineRate: 0.4 }],
      }).success,
    ).toBe(false);
    expect(
      publicDashboardDataSchema.safeParse({
        ...publicData,
        trend: [
          {
            ...insufficientTrend,
            packsObserved: 30,
            completeOpenings: 3,
            independentSources: 3,
            observedRate: 0.5,
            baselineRate: 0.4,
          },
        ],
      }).success,
    ).toBe(true);
  });

  it("has trend series suitable for a chart and table fallback", () => {
    expect(DEMO_DATA.trend.length).toBeGreaterThanOrEqual(6);
    for (const point of DEMO_DATA.trend) {
      expect(point.observedRate).toBeGreaterThanOrEqual(0);
      expect(point.observedRate).toBeLessThanOrEqual(1);
    }
  });
});
