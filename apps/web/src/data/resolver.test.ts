import { describe, expect, it, vi } from "vitest";

import { parseEnv } from "@/config/env";
import { DEMO_DATA } from "./demo";
import { resolveDashboardData } from "./resolver";

const liveEnv = parseEnv({
  DATA_MODE: "live",
  NEXT_PUBLIC_SUPABASE_URL: "https://project.supabase.co",
  NEXT_PUBLIC_SUPABASE_PUBLISHABLE_KEY: "public-key",
});

describe("resolveDashboardData", () => {
  it("serves deterministic fixtures only when DATA_MODE is demo", async () => {
    const loadLive = vi.fn();
    const result = await resolveDashboardData(parseEnv({ DATA_MODE: "demo" }), loadLive);

    expect(result).toMatchObject({ status: "ready", mode: "demo", synthetic: true });
    expect(result.status === "ready" && result.data.mode).toBe("demo");
    expect(result.status === "ready" && result.data).not.toHaveProperty("admin");
    expect(result.status === "ready" && result.data.recentActivity.every((item) => item.published)).toBe(true);
    expect(loadLive).not.toHaveBeenCalled();
  });

  it("fails closed when live mode is not configured", async () => {
    const loadLive = vi.fn();
    const result = await resolveDashboardData(parseEnv({ DATA_MODE: "live" }), loadLive);

    expect(result).toMatchObject({
      status: "unavailable",
      mode: "live",
      code: "supabase-unconfigured",
    });
    expect(result).not.toHaveProperty("data");
    expect(loadLive).not.toHaveBeenCalled();
  });

  it("does not substitute fixtures when the live provider fails", async () => {
    const result = await resolveDashboardData(liveEnv, async () => {
      throw new Error("connection details must not leak");
    });

    expect(result).toMatchObject({
      status: "unavailable",
      mode: "live",
      code: "upstream-unavailable",
    });
    expect(result.status === "unavailable" && result.message).not.toMatch(/connection details/i);
    expect(result).not.toHaveProperty("data");
  });

  it("rejects malformed live payloads", async () => {
    const result = await resolveDashboardData(liveEnv, async () => ({ mode: "live" }));

    expect(result).toMatchObject({
      status: "unavailable",
      code: "invalid-payload",
    });
  });

  it("accepts a validated aggregate-only live snapshot", async () => {
    const { admin, ...publicFixture } = DEMO_DATA;
    expect(admin).toBeDefined();
    const liveSnapshot = { ...publicFixture, mode: "live" as const };
    const result = await resolveDashboardData(liveEnv, async () => liveSnapshot);

    expect(result).toMatchObject({ status: "ready", mode: "live", synthetic: false });
    expect(result.status === "ready" && result.data.mode).toBe("live");
    expect(result.status === "ready" && result.data.recentActivity.every((item) => item.published)).toBe(true);
    expect(result.status === "ready" && result.data.recentActivity.length).toBe(
      DEMO_DATA.recentActivity.filter((item) => item.published).length,
    );
  });

  it("accepts the v3 live pipeline projection end to end", async () => {
    const { admin, ...publicFixture } = DEMO_DATA;
    expect(admin).toBeDefined();
    const observedAt = "2026-08-30T00:00:00.000Z";
    const mapCell = {
      countryCode: "US",
      countryName: "United States",
      periodStart: "2026-08-29",
      periodEnd: "2026-08-30",
      setScope: "all" as const,
      productScope: "all" as const,
      metricKey: "qualifying_hit_pack_rate" as const,
      metricVersion: "global-sir-v1",
      methodologyVersion: "global-observation-v1",
      packsObserved: 55,
      openings: 1,
      independentSources: 1,
      baselineRate: null,
      hitRate: null,
      posteriorMean: null,
      credibleInterval: null,
      deltaFromBaseline: null,
      state: "insufficient" as const,
      sampleNote: "Rate withheld below three independent sources.",
      updatedAt: observedAt,
    };
    const liveSnapshot = {
      ...publicFixture,
      mode: "live" as const,
      generatedAt: observedAt,
      summary: {
        ...publicFixture.summary,
        observedPacks: 55,
        completeOpenings: 1,
        aiValidatedSources: 0,
        trackedSets: 1,
        trackedRegions: 1,
        baselineHitRate: null,
        globalCoverage: "One country has verified current-period observations.",
        methodologyVersion: "global-observation-v1",
      },
      observations: {
        status: "collecting" as const,
        period: { start: "2026-08-29", end: "2026-08-30" },
        observedPacks: 55,
        completeOpenings: 1,
        independentSources: null,
        sourceCountryContributions: 1,
        countriesObserved: 1,
        countriesWithPublishedRate: 0,
        asOf: observedAt,
        methodologyVersion: "global-observation-v1",
        minimumPacks: 30 as const,
        minimumSources: 3 as const,
        watchMinimumPacks: 200 as const,
        metricKey: "qualifying_hit_pack_rate" as const,
      },
      mapCells: [mapCell],
      sets: [
        {
          slug: "perfect-order",
          name: "Perfect Order",
          series: "Mega Evolution",
          releaseDate: "2026-03-27",
          signal: "Rate withheld; the publication threshold is not met.",
          packsObserved: 55,
          openings: 1,
          independentSources: 1,
          baselineRate: null,
          hitRate: null,
          posteriorMean: null,
          credibleInterval: null,
          deltaFromBaseline: null,
          state: "insufficient" as const,
          sampleNote: "Rate withheld below three independent sources.",
          updatedAt: observedAt,
        },
      ],
      regions: [
        {
          slug: "us",
          name: "United States",
          countryCode: "US",
          coverage: "55 observed packs from one independent source.",
          packsObserved: mapCell.packsObserved,
          openings: mapCell.openings,
          independentSources: mapCell.independentSources,
          baselineRate: mapCell.baselineRate,
          hitRate: mapCell.hitRate,
          posteriorMean: mapCell.posteriorMean,
          credibleInterval: mapCell.credibleInterval,
          deltaFromBaseline: mapCell.deltaFromBaseline,
          state: mapCell.state,
          sampleNote: mapCell.sampleNote,
          updatedAt: mapCell.updatedAt,
        },
      ],
      retailers: [],
      batches: [],
      trend: [],
      sources: [
        {
          id: "tcgdex_catalog",
          name: "TCGdex catalog",
          kind: "catalog" as const,
          access: "public" as const,
          status: "operational" as const,
          lastCollectedAt: observedAt,
          url: "https://tcgdex.dev/",
          note: "Catalog metadata only.",
        },
        {
          id: "youtube_discovery",
          name: "YouTube global discovery",
          kind: "video" as const,
          access: "api-key" as const,
          status: "operational" as const,
          lastCollectedAt: observedAt,
          url: "https://developers.google.com/youtube/v3/docs/search/list",
          note: "One current metadata record; never used as evidence.",
        },
        {
          id: "comicbook_perfect_order_study",
          name: "ComicBook Perfect Order study",
          kind: "community" as const,
          access: "public" as const,
          status: "operational" as const,
          lastCollectedAt: observedAt,
          url: "https://comicbook.com/gaming/feature/pokemon-tcg-perfect-order-pull-rates-ex-illustration-rares-estimates",
          note: "Reviewed public study.",
        },
        {
          id: "wargamer_chaos_rising_study",
          name: "Wargamer Chaos Rising study",
          kind: "community" as const,
          access: "public" as const,
          status: "operational" as const,
          lastCollectedAt: observedAt,
          url: "https://www.wargamer.com/pokemon-trading-card-game/chaos-rising-preview",
          note: "Reviewed public study.",
        },
      ],
      services: [
        {
          id: "collector",
          name: "Collection worker",
          status: "operational" as const,
          detail: "Collector heartbeat received within the last five minutes.",
          checkedAt: observedAt,
        },
        {
          id: "scheduler",
          name: "Collection scheduler",
          status: "operational" as const,
          detail: "Scheduler heartbeat received within the last five minutes.",
          checkedAt: observedAt,
        },
        {
          id: "watchdog",
          name: "Retention watchdog",
          status: "operational" as const,
          detail: "Watchdog heartbeat received within the last five minutes.",
          checkedAt: observedAt,
        },
      ],
      recentActivity: [],
    };

    const result = await resolveDashboardData(liveEnv, async () => liveSnapshot);

    expect(result).toMatchObject({ status: "ready", mode: "live", synthetic: false });
    expect(result.status === "ready" && result.data.mapCells[0]?.countryCode).toBe("US");
    expect(result.status === "ready" && result.data.sets[0]?.name).toBe("Perfect Order");
    expect(result.status === "ready" && result.data.sources.map(({ id }) => id)).toEqual([
      "tcgdex_catalog",
      "youtube_discovery",
      "comicbook_perfect_order_study",
      "wargamer_chaos_rising_study",
    ]);
    expect(result.status === "ready" && result.data.services.map(({ id }) => id)).toEqual([
      "collector",
      "scheduler",
      "watchdog",
    ]);
  });
});
