import { describe, expect, it } from "vitest";

import { DEMO_PUBLIC_DATA } from "./demo";
import { mergePublicStudyCoverage, publicStudyCoverageSchema } from "./coverage";
import { countryDataVersionsSchema, publicDashboardDataSchema } from "./schema";

const collectedAt = "2026-08-25T02:58:00.000Z";
const syntheticJapanDataVersion = "ja · M3 · ムニキスゼロ · booster box";
const sources = [
  {
    id: "cardchill_ascended_heroes_study",
    name: "CardChill Ascended Heroes study",
    kind: "community" as const,
    access: "public" as const,
    status: "operational" as const,
    lastCollectedAt: collectedAt,
    url: "https://cardchill.com/article/ripping-10-ascended-heroes-etbs-is-the-mega-attack-pull-rate-real",
    note: "Reviewed denominator-only coverage attributed to the United Kingdom.",
  },
  {
    id: "bleedingcool_phantasmal_flames_study",
    name: "Bleeding Cool Phantasmal Flames study",
    kind: "community" as const,
    access: "public" as const,
    status: "attention" as const,
    lastCollectedAt: null,
    url: "https://bleedingcool.com/games/opening-pokemon-tcg-mega-evolution-phantasmal-flames-products",
    note: "Reviewed denominator-only coverage attributed to the United States.",
  },
  {
    id: "tcgtalk_perfect_order_study",
    name: "tcgTalk Perfect Order study",
    kind: "community" as const,
    access: "public" as const,
    status: "operational" as const,
    lastCollectedAt: collectedAt,
    url: "https://tcgtalk.com/blog/perfect-order-pull-rates-what-singapore-collectors-can-expect-1774442400232",
    note: "Reviewed denominator-only coverage attributed to Singapore's publisher country.",
  },
];

const registrySources = [
  {
    id: "comicbook_perfect_order_study",
    name: "ComicBook Perfect Order study",
    kind: "community" as const,
    access: "public" as const,
    status: "operational" as const,
    lastCollectedAt: collectedAt,
    url: "https://comicbook.com/gaming/feature/pokemon-tcg-perfect-order-pull-rates-ex-illustration-rares-estimates",
    note: "Reviewed 55-pack public study attributed to the United States.",
    coverage: {
      packsObserved: 55,
      countriesObserved: 1,
      completeOpenings: 1,
    },
  },
  {
    id: "wargamer_chaos_rising_study",
    name: "Wargamer Chaos Rising study",
    kind: "community" as const,
    access: "public" as const,
    status: "operational" as const,
    lastCollectedAt: collectedAt,
    url: "https://www.wargamer.com/pokemon-trading-card-game/chaos-rising-preview",
    note: "Reviewed 17-pack public study attributed to the United Kingdom.",
  },
  ...sources,
];

function validCoveragePayload() {
  return {
    schemaVersion: "1.0.0",
    period: { start: "2026-08-18", end: "2026-08-24" },
    countries: [
      {
        countryCode: "GB",
        countryName: "United Kingdom",
        packsObserved: 90,
        openings: 1,
        independentSources: 1,
        updatedAt: collectedAt,
      },
    ],
    sets: [
      {
        slug: "ascended-heroes",
        name: "Ascended Heroes",
        series: "Mega Evolution",
        releaseDate: "2026-02-20",
        packsObserved: 90,
        openings: 1,
        independentSources: 1,
        updatedAt: collectedAt,
      },
    ],
    sources,
  };
}

function validRegistryCoveragePayload() {
  return {
    ...validCoveragePayload(),
    schemaVersion: "2.0.0" as const,
    countries: [
      {
        countryCode: "BR",
        countryName: "Brazil",
        collectionClass: "coverage_only" as const,
        coverageAttributionBases: ["publisher_country"] as const,
        packsObserved: 91,
        openings: 2,
        independentSources: 2,
        updatedAt: collectedAt,
      },
    ],
    sources: registrySources.map((source) => ({
      ...source,
      ...("coverage" in source && source.coverage !== undefined
        ? { coverage: { ...source.coverage } }
        : {}),
    })),
  };
}

function emptyPublicSnapshot() {
  return publicDashboardDataSchema.parse({
    ...DEMO_PUBLIC_DATA,
    summary: {
      ...DEMO_PUBLIC_DATA.summary,
      observedPacks: 0,
      completeOpenings: 0,
      aiValidatedSources: 0,
      trackedRegions: 0,
      baselineHitRate: null,
      globalCoverage: "No verified country observations are published yet.",
    },
    observations: {
      ...DEMO_PUBLIC_DATA.observations,
      status: "empty",
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
    regions: [],
  });
}

function validSyntheticJapanCoveragePayload() {
  return {
    schemaVersion: "2.0.0" as const,
    period: { start: "2025-09-05", end: "2026-09-04" },
    countries: [
      {
        countryCode: "JP",
        countryName: "Japan",
        dataVersions: [syntheticJapanDataVersion],
        collectionClass: "coverage_only" as const,
        coverageAttributionBases: ["product_market"] as const,
        packsObserved: 30,
        openings: 1,
        independentSources: 1,
        updatedAt: collectedAt,
      },
    ],
    sets: [],
    sources: [
      {
        id: "synthetic_japan_parser_fixture",
        name: "Synthetic Japan parser fixture",
        kind: "community" as const,
        access: "public" as const,
        status: "paused" as const,
        lastCollectedAt: null,
        url: "https://example.com/synthetic-japan-parser-fixture",
        note: "Synthetic parser/UI fixture only; not reviewed or published evidence.",
      },
    ],
  };
}

describe("reviewed public-study coverage merge", () => {
  it("keeps payloads and snapshots without data versions backward compatible", () => {
    const coverage = publicStudyCoverageSchema.parse(validCoveragePayload());
    const snapshot = publicDashboardDataSchema.parse(DEMO_PUBLIC_DATA);

    expect(coverage.countries[0]).not.toHaveProperty("dataVersions");
    expect(snapshot.mapCells.every((cell) => cell.dataVersions === undefined)).toBe(true);
  });

  it("parses a synthetic Japanese data-version fixture without publishing a rate", () => {
    const base = emptyPublicSnapshot();
    const parsed = publicDashboardDataSchema.parse(
      mergePublicStudyCoverage(base, validSyntheticJapanCoveragePayload()),
    );
    const japan = parsed.mapCells.find((cell) => cell.countryCode === "JP");

    expect(japan).toMatchObject({
      countryName: "Japan",
      dataVersions: [syntheticJapanDataVersion],
      collectionClass: "coverage_only",
      coverageAttributionBases: ["product_market"],
      packsObserved: 30,
      openings: 1,
      independentSources: 1,
      baselineRate: null,
      hitRate: null,
      posteriorMean: null,
      credibleInterval: null,
      deltaFromBaseline: null,
      state: "insufficient",
    });
    expect(japan?.sampleNote).toContain("30 observed packs across 1 independent sources");
    expect(parsed.observations.countriesWithPublishedRate).toBe(0);
    expect(parsed.sets.some((set) => set.slug.toLowerCase() === "m3")).toBe(false);
    expect(parsed.regions.find((region) => region.countryCode === "JP")).toMatchObject({
      dataVersions: [syntheticJapanDataVersion],
      collectionClass: "coverage_only",
      coverageAttributionBases: ["product_market"],
    });
    expect(parsed.sources.find((source) => source.id === "synthetic_japan_parser_fixture"))
      .toMatchObject({
        status: "paused",
        note: "Synthetic parser/UI fixture only; not reviewed or published evidence.",
      });
  });

  it("rejects duplicate or malformed data-version labels", () => {
    const base = emptyPublicSnapshot();
    const duplicate = validSyntheticJapanCoveragePayload();
    duplicate.countries[0]!.dataVersions = [
      syntheticJapanDataVersion,
      syntheticJapanDataVersion,
    ];
    const padded = validSyntheticJapanCoveragePayload();
    padded.countries[0]!.dataVersions = [` ${syntheticJapanDataVersion}`];

    expect(mergePublicStudyCoverage(base, duplicate)).toBe(base);
    expect(mergePublicStudyCoverage(base, padded)).toBe(base);
  });

  it("accepts Japanese and Chinese labels while rejecting non-NFC or invisible text", () => {
    expect(countryDataVersionsSchema.parse([
      "ja · M5 · アビスアイ · booster box",
      "zh-Hans · M5 · 深渊之眼 · 盒",
    ])).toEqual([
      "ja · M5 · アビスアイ · booster box",
      "zh-Hans · M5 · 深渊之眼 · 盒",
    ]);
    expect(countryDataVersionsSchema.safeParse(["ja · M5 · bad\u0000label"]).success).toBe(false);
    expect(countryDataVersionsSchema.safeParse(["ja · M5 · bad\u202elabel"]).success).toBe(false);
    expect(countryDataVersionsSchema.safeParse(["ja · M5 · Cafe\u0301"]).success).toBe(false);
    expect(countryDataVersionsSchema.safeParse(["😀".repeat(240)]).success).toBe(true);
    expect(countryDataVersionsSchema.safeParse(["😀".repeat(241)]).success).toBe(false);
  });

  it("preserves and de-duplicates data versions across additive coverage merges", () => {
    const first = publicDashboardDataSchema.parse(
      mergePublicStudyCoverage(
        emptyPublicSnapshot(),
        validSyntheticJapanCoveragePayload(),
      ),
    );
    const secondPayload = {
      ...validSyntheticJapanCoveragePayload(),
      schemaVersion: "1.0.0",
      sources,
      countries: [
        {
          ...validSyntheticJapanCoveragePayload().countries[0]!,
          dataVersions: [syntheticJapanDataVersion],
        },
      ],
    };
    const second = publicDashboardDataSchema.parse(
      mergePublicStudyCoverage(first, secondPayload),
    );

    expect(second.mapCells.find((cell) => cell.countryCode === "JP")?.dataVersions).toEqual([
      syntheticJapanDataVersion,
    ]);
  });

  it("keeps a published country aggregate while adding a coverage-only set", () => {
    const originalGb = DEMO_PUBLIC_DATA.mapCells.find((cell) => cell.countryCode === "GB");
    expect(originalGb).toBeDefined();

    const merged = mergePublicStudyCoverage(DEMO_PUBLIC_DATA, validCoveragePayload());
    const parsed = publicDashboardDataSchema.parse(merged);
    const gb = parsed.mapCells.find((cell) => cell.countryCode === "GB");

    expect(gb).toEqual(originalGb);
    expect(parsed.sets.find((set) => set.slug === "ascended-heroes")).toMatchObject({
      hitRate: null,
      baselineRate: null,
      posteriorMean: null,
      credibleInterval: null,
      deltaFromBaseline: null,
      state: "insufficient",
    });
    expect(
      parsed.sources.some(
        (source) => source.id === "cardchill_ascended_heroes_study",
      ),
    ).toBe(true);
    expect(parsed.summary.observedPacks).toBe(
      parsed.mapCells.reduce((total, cell) => total + cell.packsObserved, 0),
    );
  });

  it("keeps a published set aggregate authoritative on an overlapping supplement", () => {
    const original = DEMO_PUBLIC_DATA.sets.find((set) => set.slug === "surging-sparks");
    expect(original).toBeDefined();
    const payload = validCoveragePayload();
    payload.sets[0] = {
      ...payload.sets[0]!,
      slug: "surging-sparks",
      name: "Surging Sparks",
      series: "Scarlet & Violet",
      releaseDate: "2024-11-08",
    };

    const parsed = publicDashboardDataSchema.parse(
      mergePublicStudyCoverage(DEMO_PUBLIC_DATA, payload),
    );
    expect(parsed.sets.find((set) => set.slug === "surging-sparks")).toEqual(original);
  });

  it("adds denominator-only coverage to an existing withheld country", () => {
    const original = DEMO_PUBLIC_DATA.mapCells.find((cell) => cell.countryCode === "BR");
    expect(original?.hitRate).toBeNull();
    const payload = validCoveragePayload();
    payload.countries[0] = {
      ...payload.countries[0]!,
      countryCode: "BR",
      countryName: "Brazil",
    };

    const parsed = publicDashboardDataSchema.parse(
      mergePublicStudyCoverage(DEMO_PUBLIC_DATA, payload),
    );
    expect(parsed.mapCells.find((cell) => cell.countryCode === "BR")).toMatchObject({
      packsObserved: (original?.packsObserved ?? 0) + 90,
      independentSources: (original?.independentSources ?? 0) + 1,
      hitRate: null,
      baselineRate: null,
      posteriorMean: null,
      credibleInterval: null,
      deltaFromBaseline: null,
      state: "pending",
    });
  });

  it("uses the registry projection as the authoritative denominator instead of double counting", () => {
    const original = DEMO_PUBLIC_DATA.mapCells.find((cell) => cell.countryCode === "BR");
    expect(original?.hitRate).toBeNull();

    const parsed = publicDashboardDataSchema.parse(
      mergePublicStudyCoverage(DEMO_PUBLIC_DATA, validRegistryCoveragePayload()),
    );
    expect(parsed.mapCells.find((cell) => cell.countryCode === "BR")).toMatchObject({
      collectionClass: "coverage_only",
      coverageAttributionBases: ["publisher_country"],
      packsObserved: 91,
      openings: 2,
      independentSources: 2,
      hitRate: null,
      state: "insufficient",
    });
    expect(parsed.sources).toEqual(
      expect.arrayContaining([
        expect.objectContaining({ id: "comicbook_perfect_order_study" }),
        expect.objectContaining({ id: "tcgtalk_perfect_order_study" }),
      ]),
    );
    expect(
      parsed.sources.find((source) => source.id === "comicbook_perfect_order_study")
        ?.coverage,
    ).toEqual({
      packsObserved: 55,
      countriesObserved: 1,
      completeOpenings: 1,
    });
  });

  it("replaces only a mentioned v2 coverage row and preserves unrelated cells and inference", () => {
    const originalBrazil = DEMO_PUBLIC_DATA.mapCells.find((cell) => cell.countryCode === "BR");
    const originalGermany = DEMO_PUBLIC_DATA.mapCells.find((cell) => cell.countryCode === "DE");
    expect(originalBrazil).toBeDefined();
    expect(originalGermany).toBeDefined();

    const payload = validRegistryCoveragePayload();
    const merged = publicDashboardDataSchema.parse(
      mergePublicStudyCoverage(DEMO_PUBLIC_DATA, payload),
    );
    const brazil = merged.mapCells.find((cell) => cell.countryCode === "BR");
    const germany = merged.mapCells.find((cell) => cell.countryCode === "DE");

    expect(merged.mapCells).toHaveLength(DEMO_PUBLIC_DATA.mapCells.length);
    expect(germany).toEqual(originalGermany);
    expect(brazil).toMatchObject({
      packsObserved: 91,
      openings: 2,
      independentSources: 2,
      collectionClass: "coverage_only",
      coverageAttributionBases: ["publisher_country"],
      baselineRate: originalBrazil?.baselineRate,
      hitRate: originalBrazil?.hitRate,
      posteriorMean: originalBrazil?.posteriorMean,
      credibleInterval: originalBrazil?.credibleInterval,
      deltaFromBaseline: originalBrazil?.deltaFromBaseline,
    });
    expect(merged.regions.find((region) => region.countryCode === "BR")).toMatchObject({
      collectionClass: "coverage_only",
      coverageAttributionBases: ["publisher_country"],
    });
  });

  it("accepts only complete public source coverage and rejects rate-like fields", () => {
    const payload = validRegistryCoveragePayload();
    const parsed = publicDashboardDataSchema.parse(
      mergePublicStudyCoverage(DEMO_PUBLIC_DATA, payload),
    );
    expect(
      parsed.sources.find((source) => source.id === "comicbook_perfect_order_study")
        ?.coverage?.packsObserved,
    ).toBe(55);

    const unsafe = validRegistryCoveragePayload();
    unsafe.sources[0] = {
      ...unsafe.sources[0]!,
      coverage: {
        packsObserved: 55,
        countriesObserved: 1,
        completeOpenings: 1,
        hitRate: 0.02,
      },
    } as unknown as typeof unsafe.sources[number];
    expect(mergePublicStudyCoverage(DEMO_PUBLIC_DATA, unsafe)).toBe(DEMO_PUBLIC_DATA);
  });

  it("allows an exact reviewed source identity to replace its legacy source health row", () => {
    const payload = validRegistryCoveragePayload();
    const collidingBase = {
      ...DEMO_PUBLIC_DATA,
      sources: [
        ...DEMO_PUBLIC_DATA.sources.filter((source) => source.id !== "tcgdex"),
        registrySources[0]!,
      ],
    };

    const merged = mergePublicStudyCoverage(collidingBase, payload);
    expect(merged).not.toBe(collidingBase);
    expect(publicDashboardDataSchema.parse(merged).sources).toEqual(
      expect.arrayContaining([
        expect.objectContaining({ id: "comicbook_perfect_order_study" }),
      ]),
    );
  });

  it("ignores malformed or mismatched-period coverage without destabilizing v3", () => {
    expect(mergePublicStudyCoverage(DEMO_PUBLIC_DATA, { countries: [] })).toBe(
      DEMO_PUBLIC_DATA,
    );
    expect(
      mergePublicStudyCoverage(DEMO_PUBLIC_DATA, {
        schemaVersion: "1.0.0",
        period: { start: "2026-08-19", end: "2026-08-25" },
        countries: [],
        sets: [],
        sources,
      }),
    ).toBe(DEMO_PUBLIC_DATA);
  });

  it("rejects unreviewed identities, non-ISO countries, and base source collisions", () => {
    const invalidCountry = validCoveragePayload();
    invalidCountry.countries[0] = {
      ...invalidCountry.countries[0]!,
      countryCode: "ZZ",
    };
    expect(mergePublicStudyCoverage(DEMO_PUBLIC_DATA, invalidCountry)).toBe(
      DEMO_PUBLIC_DATA,
    );

    const invalidSource = validCoveragePayload();
    invalidSource.sources = [
      { ...sources[0]!, id: "unreviewed_source", url: "ftp://example.com/evidence" },
      sources[1]!,
      sources[2]!,
    ];
    expect(mergePublicStudyCoverage(DEMO_PUBLIC_DATA, invalidSource)).toBe(
      DEMO_PUBLIC_DATA,
    );

    const collidingBase = {
      ...DEMO_PUBLIC_DATA,
      sources: [...DEMO_PUBLIC_DATA.sources, sources[0]!],
    };
    expect(mergePublicStudyCoverage(collidingBase, validCoveragePayload())).toBe(
      collidingBase,
    );
  });
});
