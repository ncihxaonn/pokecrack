import { z } from "zod";

import { isIsoAlpha2 } from "./iso-alpha2";
import { publicDashboardDataSchema } from "./schema";
import type {
  CountryMapCell,
  PublicDashboardData,
  PublicSource,
  SetMetric,
} from "./types";

const isoDate = z.string().regex(/^\d{4}-\d{2}-\d{2}$/);
const isoDateTime = z.string().datetime({ offset: true });
const publicHttpUrl = z.string().url().refine((value) => {
  try {
    const protocol = new URL(value).protocol;
    return protocol === "http:" || protocol === "https:";
  } catch {
    return false;
  }
}, "Public URLs must use http or https");
const coverageSourceIds = [
  "cardchill_ascended_heroes_study",
  "bleedingcool_phantasmal_flames_study",
  "tcgtalk_perfect_order_study",
] as const;
const coverageSourceIdentity: Record<
  (typeof coverageSourceIds)[number],
  { readonly name: string; readonly url: string }
> = {
  cardchill_ascended_heroes_study: {
    name: "CardChill Ascended Heroes study",
    url: "https://cardchill.com/article/ripping-10-ascended-heroes-etbs-is-the-mega-attack-pull-rate-real",
  },
  bleedingcool_phantasmal_flames_study: {
    name: "Bleeding Cool Phantasmal Flames study",
    url: "https://bleedingcool.com/games/opening-pokemon-tcg-mega-evolution-phantasmal-flames-products",
  },
  tcgtalk_perfect_order_study: {
    name: "tcgTalk Perfect Order study",
    url: "https://tcgtalk.com/blog/perfect-order-pull-rates-what-singapore-collectors-can-expect-1774442400232",
  },
};

const coverageMetric = z
  .object({
    packsObserved: z.number().int().positive(),
    openings: z.number().int().positive(),
    independentSources: z.number().int().positive(),
    updatedAt: isoDateTime,
  })
  .strict()
  .refine((value) => value.openings <= value.packsObserved)
  .refine((value) => value.independentSources <= value.openings);

const coverageCountry = coverageMetric.extend({
  countryCode: z.string().refine(
    isIsoAlpha2,
    "Country code must be an official ISO alpha-2 code",
  ),
  countryName: z.string().min(1).max(160),
});

const coverageSet = coverageMetric.extend({
  slug: z.string().min(1).max(160),
  name: z.string().min(1).max(160),
  series: z.string().min(1).max(160),
  releaseDate: isoDate,
});

const reviewedSourceCoverage = z
  .object({
    packsObserved: z.number().int().positive().max(1_000_000),
    countriesObserved: z.number().int().positive().max(249),
    completeOpenings: z.number().int().positive().max(1_000_000),
  })
  .strict()
  .superRefine((coverage, context) => {
    if (coverage.completeOpenings > coverage.packsObserved) {
      context.addIssue({
        code: z.ZodIssueCode.custom,
        message: "Reviewed source openings cannot exceed observed packs",
        path: ["completeOpenings"],
      });
    }
    if (coverage.countriesObserved > coverage.completeOpenings) {
      context.addIssue({
        code: z.ZodIssueCode.custom,
        message: "Reviewed source countries cannot exceed complete openings",
        path: ["countriesObserved"],
      });
    }
  });

const reviewedCoverageSource = z
  .object({
    id: z.string().regex(/^[a-z][a-z0-9_-]{0,119}$/),
    name: z.string().min(1).max(160),
    kind: z.literal("community"),
    access: z.literal("public"),
    status: z.enum(["operational", "delayed", "attention", "paused"]),
    lastCollectedAt: isoDateTime.nullable(),
    url: publicHttpUrl,
    note: z.string().min(1).max(500),
    coverage: reviewedSourceCoverage.optional(),
  })
  .strict();

const legacyCoverageSource = reviewedCoverageSource
  .omit({ coverage: true })
  .extend({ id: z.enum(coverageSourceIds) })
  .superRefine((source, context) => {
    const expected = coverageSourceIdentity[source.id];
    if (source.name !== expected.name) {
      context.addIssue({
        code: z.ZodIssueCode.custom,
        message: "Coverage source name does not match its reviewed identity",
        path: ["name"],
      });
    }
    if (source.url !== expected.url) {
      context.addIssue({
        code: z.ZodIssueCode.custom,
        message: "Coverage source URL does not match its reviewed identity",
        path: ["url"],
      });
    }
  });

const coverageEnvelope = z
  .object({
    period: z.object({ start: isoDate, end: isoDate }).strict(),
    countries: z.array(coverageCountry).max(249),
    sets: z.array(coverageSet).max(100),
  })
  .strict();

const publicStudyCoverageV1Schema = coverageEnvelope.extend({
  schemaVersion: z.literal("1.0.0"),
  sources: z.array(legacyCoverageSource).length(3),
});

const publicStudyCoverageV2Schema = coverageEnvelope.extend({
  schemaVersion: z.literal("2.0.0"),
  sources: z.array(reviewedCoverageSource).min(1).max(100),
});

export const publicStudyCoverageSchema = z
  .union([publicStudyCoverageV1Schema, publicStudyCoverageV2Schema])
  .superRefine((value, context) => {
    if (value.period.start > value.period.end) {
      context.addIssue({
        code: z.ZodIssueCode.custom,
        message: "Coverage period start cannot follow its end",
        path: ["period"],
      });
    }
    if (new Set(value.countries.map((row) => row.countryCode)).size !== value.countries.length) {
      context.addIssue({
        code: z.ZodIssueCode.custom,
        message: "Coverage countries must be unique",
        path: ["countries"],
      });
    }
    if (new Set(value.sets.map((row) => row.slug)).size !== value.sets.length) {
      context.addIssue({
        code: z.ZodIssueCode.custom,
        message: "Coverage sets must be unique",
        path: ["sets"],
      });
    }
    if (new Set(value.sources.map((row) => row.id)).size !== value.sources.length) {
      context.addIssue({
        code: z.ZodIssueCode.custom,
        message: "Coverage sources must be unique",
        path: ["sources"],
      });
    }
  });

export type PublicStudyCoverage = z.infer<typeof publicStudyCoverageSchema>;

function laterTimestamp(left: string | null, right: string): string {
  if (left === null) return right;
  return Date.parse(left) >= Date.parse(right) ? left : right;
}

function withheldState(packs: number, sources: number): "insufficient" | "pending" {
  return packs < 30 || sources < 3 ? "insufficient" : "pending";
}

function sampleNote(packs: number, sources: number): string {
  if (packs < 30 || sources < 3) {
    return `Rate withheld: ${packs} observed packs across ${sources} independent sources. Publication requires at least 30 packs and three sources; coverage-only reviews do not publish inference.`;
  }
  return "Coverage threshold met, but coverage-only evidence cannot publish a rate; statistical-ledger promotion and the reviewed aggregate publisher are still required.";
}

function mergeCountry(
  current: CountryMapCell | undefined,
  coverage: PublicStudyCoverage["countries"][number],
  period: PublicStudyCoverage["period"],
  replaceWithAuthoritativeCoverage: boolean,
): CountryMapCell {
  // The aggregate publisher owns every inference field and its matching
  // denominator. Coverage-only evidence may populate a missing/withheld row,
  // but it must never rewrite an already-published aggregate.
  if (current !== undefined && current.hitRate !== null) return current;
  const packsObserved = replaceWithAuthoritativeCoverage
    ? coverage.packsObserved
    : (current?.packsObserved ?? 0) + coverage.packsObserved;
  const openings = replaceWithAuthoritativeCoverage
    ? coverage.openings
    : (current?.openings ?? 0) + coverage.openings;
  const independentSources = replaceWithAuthoritativeCoverage
    ? coverage.independentSources
    : (current?.independentSources ?? 0) + coverage.independentSources;
  return {
    countryCode: coverage.countryCode,
    countryName: current?.countryName ?? coverage.countryName,
    periodStart: period.start,
    periodEnd: period.end,
    setScope: "all",
    productScope: "all",
    metricKey: "qualifying_hit_pack_rate",
    metricVersion: "global-sir-v1",
    methodologyVersion: "global-observation-v1",
    packsObserved,
    openings,
    independentSources,
    baselineRate: null,
    hitRate: null,
    posteriorMean: null,
    credibleInterval: null,
    deltaFromBaseline: null,
    state: withheldState(packsObserved, independentSources),
    sampleNote: sampleNote(packsObserved, independentSources),
    updatedAt: laterTimestamp(current?.updatedAt ?? null, coverage.updatedAt),
  };
}

function mergeSet(
  current: SetMetric | undefined,
  coverage: PublicStudyCoverage["sets"][number],
  replaceWithAuthoritativeCoverage: boolean,
): SetMetric {
  if (current !== undefined && current.hitRate !== null) return current;
  const packsObserved = replaceWithAuthoritativeCoverage
    ? coverage.packsObserved
    : (current?.packsObserved ?? 0) + coverage.packsObserved;
  const openings = replaceWithAuthoritativeCoverage
    ? coverage.openings
    : (current?.openings ?? 0) + coverage.openings;
  const independentSources = replaceWithAuthoritativeCoverage
    ? coverage.independentSources
    : (current?.independentSources ?? 0) + coverage.independentSources;
  return {
    slug: coverage.slug,
    name: current?.name ?? coverage.name,
    series: current?.series ?? coverage.series,
    releaseDate: current?.releaseDate ?? coverage.releaseDate,
    signal: "Coverage-only review; rate and inference remain withheld.",
    packsObserved,
    openings,
    independentSources,
    baselineRate: null,
    hitRate: null,
    posteriorMean: null,
    credibleInterval: null,
    deltaFromBaseline: null,
    state: withheldState(packsObserved, independentSources),
    sampleNote: sampleNote(packsObserved, independentSources),
    updatedAt: laterTimestamp(current?.updatedAt ?? null, coverage.updatedAt),
  };
}

export function mergePublicStudyCoverage(
  snapshot: unknown,
  coveragePayload: unknown,
): unknown {
  const snapshotResult = publicDashboardDataSchema.safeParse(snapshot);
  const coverageResult = publicStudyCoverageSchema.safeParse(coveragePayload);
  if (!snapshotResult.success || !coverageResult.success) return snapshot;

  const base = snapshotResult.data;
  const coverage = coverageResult.data;
  const replaceWithAuthoritativeCoverage = coverage.schemaVersion === "2.0.0";
  if (
    base.observations.period !== null &&
    (base.observations.period.start !== coverage.period.start ||
      base.observations.period.end !== coverage.period.end)
  ) {
    return snapshot;
  }
  const sourceById = new Map<string, PublicSource>(
    base.sources.map((source) => [source.id, source]),
  );
  for (const source of coverage.sources) {
    const current = sourceById.get(source.id);
    if (
      current !== undefined &&
      (!replaceWithAuthoritativeCoverage ||
        current.name !== source.name ||
        current.kind !== source.kind ||
        current.access !== source.access ||
        current.url !== source.url)
    ) {
      return snapshot;
    }
    sourceById.set(source.id, source);
  }

  if (coverage.countries.length === 0 && !replaceWithAuthoritativeCoverage) {
    return { ...base, sources: [...sourceById.values()] } satisfies PublicDashboardData;
  }

  const countryByCode = new Map<string, CountryMapCell>(
    base.mapCells.map((cell) => [cell.countryCode, cell]),
  );
  for (const row of coverage.countries) {
    countryByCode.set(
      row.countryCode,
      mergeCountry(
        countryByCode.get(row.countryCode),
        row,
        coverage.period,
        replaceWithAuthoritativeCoverage,
      ),
    );
  }
  const mapCells = [...countryByCode.values()].sort(
    (left, right) =>
      left.countryName.localeCompare(right.countryName) ||
      left.countryCode.localeCompare(right.countryCode),
  );

  const setBySlug = new Map<string, SetMetric>(base.sets.map((set) => [set.slug, set]));
  for (const row of coverage.sets) {
    setBySlug.set(
      row.slug,
      mergeSet(setBySlug.get(row.slug), row, replaceWithAuthoritativeCoverage),
    );
  }
  const sets = [...setBySlug.values()].sort(
    (left, right) =>
      right.releaseDate.localeCompare(left.releaseDate) || left.name.localeCompare(right.name),
  );

  const observedPacks = mapCells.reduce((total, cell) => total + cell.packsObserved, 0);
  const completeOpenings = mapCells.reduce((total, cell) => total + cell.openings, 0);
  const sourceCountryContributions = mapCells.reduce(
    (total, cell) => total + cell.independentSources,
    0,
  );
  const countriesWithPublishedRate = mapCells.filter(
    (cell) => cell.hitRate !== null,
  ).length;
  const asOf = mapCells.reduce<string | null>(
    (latest, cell) => laterTimestamp(latest, cell.updatedAt),
    null,
  );
  const regions = mapCells.map((cell) => ({
    slug: cell.countryCode.toLowerCase(),
    name: cell.countryName,
    countryCode: cell.countryCode,
    coverage: `${cell.packsObserved} observed packs from ${cell.independentSources} independent sources in the current global period.`,
    packsObserved: cell.packsObserved,
    openings: cell.openings,
    independentSources: cell.independentSources,
    baselineRate: cell.baselineRate,
    hitRate: cell.hitRate,
    posteriorMean: cell.posteriorMean,
    credibleInterval: cell.credibleInterval,
    deltaFromBaseline: cell.deltaFromBaseline,
    state: cell.state,
    sampleNote: cell.sampleNote,
    updatedAt: cell.updatedAt,
  }));

  const candidate = {
    ...base,
    summary: {
      ...base.summary,
      observedPacks,
      completeOpenings,
      trackedSets: sets.length,
      trackedRegions: mapCells.length,
      baselineHitRate: countriesWithPublishedRate === 0 ? null : base.summary.baselineHitRate,
      globalCoverage: `${mapCells.length} countries have verified observations in the current global period; ${countriesWithPublishedRate} publish a rate.`,
      methodologyVersion: "global-observation-v1",
    },
    observations: {
      ...base.observations,
      status: countriesWithPublishedRate > 0 ? "published" : "collecting",
      period: coverage.period,
      observedPacks,
      completeOpenings,
      sourceCountryContributions,
      countriesObserved: mapCells.length,
      countriesWithPublishedRate,
      asOf,
      methodologyVersion: "global-observation-v1",
    },
    mapCells,
    sets,
    regions,
    sources: [...sourceById.values()],
  } satisfies PublicDashboardData;
  const merged = publicDashboardDataSchema.safeParse(candidate);
  return merged.success ? merged.data : snapshot;
}
