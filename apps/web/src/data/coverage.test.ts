import { describe, expect, it } from "vitest";

import { DEMO_PUBLIC_DATA } from "./demo";
import { mergePublicStudyCoverage } from "./coverage";
import { publicDashboardDataSchema } from "./schema";

const collectedAt = "2026-08-25T02:58:00.000Z";
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

describe("reviewed public-study coverage merge", () => {
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
