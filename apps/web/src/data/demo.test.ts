import { describe, expect, it } from "vitest";

import { DEMO_DATA, DEMO_PUBLIC_DATA } from "./demo";
import { publicDashboardDataSchema } from "./schema";

describe("DEMO_DATA", () => {
  it("contains deterministic dashboard coverage and all required evidence states", () => {
    expect(DEMO_DATA.mode).toBe("demo");
    expect(DEMO_DATA.schemaVersion).toBe("2.0.0");
    expect(DEMO_DATA.summary.observedPacks).toBeGreaterThan(1_000);
    expect(DEMO_DATA.summary.completeOpenings).toBeGreaterThan(0);
    expect(DEMO_DATA.summary.aiValidatedSources).toBeGreaterThan(0);
    expect(DEMO_DATA.summary.trackedSets).toBe(DEMO_DATA.sets.length);
    expect(DEMO_DATA.summary.trackedRegions).toBe(DEMO_DATA.mapCells.length);
    expect(DEMO_DATA.summary.batchSightings).toBe(DEMO_DATA.batches.length);
    expect(DEMO_DATA.summary.globalCoverage).toMatch(/continents/i);
    expect(DEMO_DATA.summary.methodologyVersion).toMatch(/^global-/);
    expect(DEMO_DATA.catalog.catalogOnly).toBe(true);
    expect(DEMO_DATA.catalog.setCount).toBe(DEMO_DATA.catalog.sets.length);
    expect(DEMO_DATA.mapCells.map((item) => item.countryCode)).toEqual(
      expect.arrayContaining(["AU", "BR", "DE", "GB", "JP", "US"]),
    );
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

  it("keeps unpublished activity internal and filters it at the public schema boundary", () => {
    expect(DEMO_DATA.recentActivity.some((item) => item.published === false)).toBe(true);
    expect(DEMO_PUBLIC_DATA.recentActivity.every((item) => item.published)).toBe(true);
    expect(DEMO_PUBLIC_DATA.recentActivity.map((item) => item.id)).not.toContain(
      "activity-web-perth-004",
    );

    const { admin, ...unfilteredPublicShape } = DEMO_DATA;
    expect(admin).toBeDefined();
    const parsed = publicDashboardDataSchema.parse(unfilteredPublicShape);
    expect(parsed.recentActivity.every((item) => item.published)).toBe(true);
    expect(parsed.recentActivity).toHaveLength(DEMO_PUBLIC_DATA.recentActivity.length);
  });

  it("accepts only http and https public external links", () => {
    expect(publicDashboardDataSchema.safeParse(DEMO_PUBLIC_DATA).success).toBe(true);
    expect(publicDashboardDataSchema.safeParse({
      ...DEMO_PUBLIC_DATA,
      sources: DEMO_PUBLIC_DATA.sources.map((source, index) =>
        index === 0 ? { ...source, url: "javascript:alert(document.domain)" } : source,
      ),
    }).success).toBe(false);
    expect(publicDashboardDataSchema.safeParse({
      ...DEMO_PUBLIC_DATA,
      recentActivity: DEMO_PUBLIC_DATA.recentActivity.map((activity, index) =>
        index === 0 ? { ...activity, sourceUrl: "data:text/html,unsafe" } : activity,
      ),
    }).success).toBe(false);
  });

  it("keeps the legacy regional slice Australia-only while the v2 map is global", () => {
    expect(DEMO_DATA.regions.every((item) => item.countryCode === "AU")).toBe(true);
    expect(new Set(DEMO_DATA.mapCells.map((item) => item.countryCode)).size).toBeGreaterThan(1);
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
      ...DEMO_DATA.mapCells,
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
    const globalRegion = {
      ...publicData,
      regions: publicData.regions.map((item, index) =>
        index === 0 ? { ...item, countryCode: "US" } : item,
      ),
    };
    expect(publicDashboardDataSchema.safeParse(globalRegion).success).toBe(true);
    const invalidRegionCode = {
      ...publicData,
      regions: publicData.regions.map((item, index) =>
        index === 0 ? { ...item, countryCode: "UK" } : item,
      ),
    };
    expect(publicDashboardDataSchema.safeParse(invalidRegionCode).success).toBe(false);
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

  it("keeps threshold-sufficient evidence visible while publication is pending", () => {
    const { admin, ...publicData } = DEMO_DATA;
    expect(admin).toBeDefined();
    const pending = {
      ...publicData,
      sets: publicData.sets.map((item, index) =>
        index === 0
          ? {
              ...item,
              baselineRate: null,
              hitRate: null,
              posteriorMean: null,
              credibleInterval: null,
              deltaFromBaseline: null,
              state: "pending" as const,
            }
          : item,
      ),
    };
    expect(publicDashboardDataSchema.safeParse(pending).success).toBe(true);

    const leakingInference = {
      ...pending,
      sets: pending.sets.map((item, index) =>
        index === 0 ? { ...item, hitRate: 0.2 } : item,
      ),
    };
    expect(publicDashboardDataSchema.safeParse(leakingInference).success).toBe(false);
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
        observedPacks: 0,
        completeOpenings: 0,
        aiValidatedSources: 0,
        trackedRegions: 0,
        baselineHitRate: null,
      },
      observations: {
        ...publicData.observations,
        status: "empty" as const,
        period: null,
        observedPacks: 0,
        completeOpenings: 0,
        sourceCountryContributions: 0,
        countriesObserved: 0,
        countriesWithPublishedRate: 0,
        asOf: null,
        methodologyVersion: null,
      },
      mapCells: [],
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
      ...DEMO_DATA.mapCells.map((item) => `country:${item.countryCode}`),
    ];

    expect(new Set(slugs).size).toBe(slugs.length);
  });

  it("rejects non-ISO map codes, duplicate countries, and mixed periods", () => {
    const invalidCode = {
      ...DEMO_PUBLIC_DATA,
      mapCells: DEMO_PUBLIC_DATA.mapCells.map((cell, index) =>
        index === 0 ? { ...cell, countryCode: "UK" } : cell,
      ),
    };
    expect(publicDashboardDataSchema.safeParse(invalidCode).success).toBe(false);

    const duplicate = {
      ...DEMO_PUBLIC_DATA,
      mapCells: DEMO_PUBLIC_DATA.mapCells.map((cell, index) =>
        index === 0 ? { ...cell, countryCode: "BR" } : cell,
      ),
    };
    expect(publicDashboardDataSchema.safeParse(duplicate).success).toBe(false);

    const mixedPeriod = {
      ...DEMO_PUBLIC_DATA,
      mapCells: DEMO_PUBLIC_DATA.mapCells.map((cell, index) =>
        index === 0 ? { ...cell, periodEnd: "2026-08-23" } : cell,
      ),
    };
    expect(publicDashboardDataSchema.safeParse(mixedPeriod).success).toBe(false);
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
