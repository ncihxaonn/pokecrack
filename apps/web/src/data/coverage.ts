import { z } from "zod";

import { isIsoAlpha2 } from "./iso-alpha2";
import {
  countryDataVersionsSchema,
  coverageAttributionBasesSchema,
  publicDashboardDataSchema,
  unknownLocationCoverageSchema,
} from "./schema";
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
  dataVersions: countryDataVersionsSchema.optional(),
  collectionClass: z.literal("coverage_only").optional(),
  coverageAttributionBases: coverageAttributionBasesSchema.optional(),
});

const coverageCountryV2 = coverageCountry.safeExtend({
  collectionClass: z.literal("coverage_only"),
  coverageAttributionBases: coverageAttributionBasesSchema,
});

const directObservedRate = {
  ratePacksObserved: z.number().int().positive().max(1_000_000).optional(),
  qualifyingHitPacks: z.number().int().nonnegative().max(1_000_000).optional(),
  observedRate: z.number().min(0).max(1).optional(),
} as const;

function validateDirectObservedRate(
  value: {
    readonly packsObserved: number;
    readonly ratePacksObserved?: number;
    readonly qualifyingHitPacks?: number;
    readonly observedRate?: number;
  },
  context: z.RefinementCtx,
) {
  const fields = [
    value.ratePacksObserved,
    value.qualifyingHitPacks,
    value.observedRate,
  ];
  const present = fields.filter((field) => field !== undefined).length;
  if (present !== 0 && present !== fields.length) {
    context.addIssue({
      code: z.ZodIssueCode.custom,
      message: "Direct observed rates require the complete raw-rate tuple",
    });
    return;
  }
  if (present === 0) return;
  if (value.ratePacksObserved! > value.packsObserved) {
    context.addIssue({
      code: z.ZodIssueCode.custom,
      message: "Rate-sample packs cannot exceed all observed packs",
      path: ["ratePacksObserved"],
    });
  }
  if (value.qualifyingHitPacks! > value.ratePacksObserved!) {
    context.addIssue({
      code: z.ZodIssueCode.custom,
      message: "Qualifying-hit packs cannot exceed rate-sample packs",
      path: ["qualifyingHitPacks"],
    });
  }
  if (
    Math.abs(
      value.observedRate! -
      value.qualifyingHitPacks! / value.ratePacksObserved!,
    ) > 1e-12
  ) {
    context.addIssue({
      code: z.ZodIssueCode.custom,
      message: "Observed rate must equal its exact numerator divided by denominator",
      path: ["observedRate"],
    });
  }
}

const coverageCountryV3 = coverageMetric.extend({
  countryCode: z.string().refine(
    isIsoAlpha2,
    "Country code must be an official ISO alpha-2 code",
  ),
  countryName: z.string().min(1).max(160),
  dataVersions: countryDataVersionsSchema.optional(),
  collectionClass: z.enum(["coverage_only", "observed_sample", "mixed"]),
  coverageAttributionBases: coverageAttributionBasesSchema,
  ...directObservedRate,
}).superRefine(validateDirectObservedRate);

const coverageSet = coverageMetric.extend({
  slug: z.string().min(1).max(160),
  name: z.string().min(1).max(160),
  series: z.string().min(1).max(160),
  releaseDate: isoDate,
});

const reviewedSourceCoverage = z
  .object({
    packsObserved: z.number().int().positive().max(1_000_000),
    countriesObserved: z.number().int().nonnegative().max(249),
    completeOpenings: z.number().int().positive().max(1_000_000),
    ...directObservedRate,
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
    validateDirectObservedRate(coverage, context);
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
  countries: z.array(coverageCountryV2).max(249),
  sources: z.array(reviewedCoverageSource).min(1).max(100),
});

const publicStudyCoverageV3Schema = coverageEnvelope.extend({
  schemaVersion: z.literal("3.0.0"),
  countries: z.array(coverageCountryV3).max(249),
  sources: z.array(reviewedCoverageSource).min(1).max(100),
});

const publicStudyCoverageV4Schema = coverageEnvelope.extend({
  schemaVersion: z.literal("4.0.0"),
  countries: z.array(coverageCountryV3).max(249),
  sources: z.array(reviewedCoverageSource).min(1).max(1_000),
  unknownLocation: unknownLocationCoverageSchema.nullable(),
});

export const publicStudyCoverageSchema = z
  .union([
    publicStudyCoverageV1Schema,
    publicStudyCoverageV2Schema,
    publicStudyCoverageV3Schema,
    publicStudyCoverageV4Schema,
  ])
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

function sampleNote(
  packs: number,
  sources: number,
  rawRate?: Readonly<{ ratePacksObserved: number; qualifyingHitPacks: number }>,
): string {
  if (rawRate !== undefined) {
    const rate = rawRate.qualifyingHitPacks / rawRate.ratePacksObserved;
    return `Direct observed sample: ${rawRate.qualifyingHitPacks} qualifying-hit ${rawRate.qualifyingHitPacks === 1 ? "pack" : "packs"} among ${rawRate.ratePacksObserved} eligible rate-sample packs (${(rate * 100).toFixed(2)}%). This descriptive sample rate is not a representative probability, baseline comparison, posterior estimate, or anomaly signal.`;
  }
  if (packs < 30 || sources < 3) {
    return `No exact normalized numerator is available for these ${packs} observed packs across ${sources} independent ${sources === 1 ? "source" : "sources"}; no sample rate or inference is shown.`;
  }
  return "Coverage is verified, but no exact normalized numerator is available; no sample rate or inference is shown.";
}

function mergeDataVersions(
  current: readonly string[] | undefined,
  incoming: readonly string[] | undefined,
  replaceWithAuthoritativeCoverage: boolean,
): readonly string[] | undefined {
  if (incoming === undefined) return current;
  if (replaceWithAuthoritativeCoverage) return [...incoming];
  return [...new Set([...(current ?? []), ...incoming])];
}

type CoverageOverlay = Pick<
  CountryMapCell,
  "dataVersions" | "collectionClass" | "coverageAttributionBases"
>;

function mergeCoverageOverlay(
  current: CoverageOverlay | undefined,
  coverage: PublicStudyCoverage["countries"][number],
  replaceCoverageOverlay: boolean,
): CoverageOverlay {
  const dataVersions = mergeDataVersions(
    current?.dataVersions,
    coverage.dataVersions,
    replaceCoverageOverlay,
  );
  const coverageAttributionBases = coverage.coverageAttributionBases === undefined
    ? current?.coverageAttributionBases
    : replaceCoverageOverlay
      ? [...coverage.coverageAttributionBases]
      : [...new Set([
        ...(current?.coverageAttributionBases ?? []),
        ...coverage.coverageAttributionBases,
      ])];
  return {
    ...(dataVersions === undefined ? {} : { dataVersions }),
    ...(coverage.collectionClass === undefined
      ? current?.collectionClass === undefined
        ? {}
        : { collectionClass: current.collectionClass }
      : { collectionClass: coverage.collectionClass }),
    ...(coverageAttributionBases === undefined
      ? {}
      : { coverageAttributionBases }),
  };
}

function mergeCountry(
  current: CountryMapCell | undefined,
  coverage: PublicStudyCoverage["countries"][number],
  period: PublicStudyCoverage["period"],
  replaceCoverageOverlay: boolean,
): CountryMapCell {
  // A fully published aggregate remains authoritative for every inference
  // field. Coverage v3 may add only a descriptive, exact numerator/denominator
  // rate to a row whose baseline/posterior signal is still unpublished.
  const coverageOverlay = mergeCoverageOverlay(
    current,
    coverage,
    replaceCoverageOverlay,
  );
  if (
    current !== undefined &&
    current.hitRate !== null &&
    current.baselineRate !== null &&
    current.posteriorMean !== null &&
    current.credibleInterval !== null &&
    current.deltaFromBaseline !== null
  ) {
    return current;
  }
  const packsObserved = replaceCoverageOverlay
    ? coverage.packsObserved
    : (current?.packsObserved ?? 0) + coverage.packsObserved;
  const openings = replaceCoverageOverlay
    ? coverage.openings
    : (current?.openings ?? 0) + coverage.openings;
  const independentSources = replaceCoverageOverlay
    ? coverage.independentSources
    : (current?.independentSources ?? 0) + coverage.independentSources;
  const incomingRawRate = "observedRate" in coverage &&
    coverage.observedRate !== undefined &&
    coverage.ratePacksObserved !== undefined &&
    coverage.qualifyingHitPacks !== undefined
    ? {
        observedRate: coverage.observedRate,
        ratePacksObserved: coverage.ratePacksObserved,
        qualifyingHitPacks: coverage.qualifyingHitPacks,
      }
    : undefined;
  const existingRawRate = current?.hitRate !== null &&
    current?.hitRate !== undefined &&
    current.ratePacksObserved !== undefined &&
    current.qualifyingHitPacks !== undefined
    ? {
        observedRate: current.hitRate,
        ratePacksObserved: current.ratePacksObserved,
        qualifyingHitPacks: current.qualifyingHitPacks,
      }
    : undefined;
  const rawRate = incomingRawRate ?? existingRawRate;
  const base = current ?? {
    periodStart: period.start,
    periodEnd: period.end,
    setScope: "all" as const,
    productScope: "all" as const,
    metricKey: "qualifying_hit_pack_rate" as const,
    metricVersion: "global-sir-v1",
    methodologyVersion: "global-observation-v1",
    baselineRate: null,
    hitRate: null,
    posteriorMean: null,
    credibleInterval: null,
    deltaFromBaseline: null,
  };
  return {
    ...base,
    countryCode: coverage.countryCode,
    countryName: current?.countryName ?? coverage.countryName,
    ...coverageOverlay,
    periodStart: current?.periodStart ?? period.start,
    periodEnd: current?.periodEnd ?? period.end,
    packsObserved,
    openings,
    independentSources,
    ...(rawRate === undefined
      ? { hitRate: null }
      : {
          ratePacksObserved: rawRate.ratePacksObserved,
          qualifyingHitPacks: rawRate.qualifyingHitPacks,
          hitRate: rawRate.observedRate,
        }),
    state: withheldState(packsObserved, independentSources),
    sampleNote: sampleNote(packsObserved, independentSources, rawRate),
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
  const unknownLocation = coverage.schemaVersion === "4.0.0"
    ? coverage.unknownLocation : null;
  const replaceRegistryCoverageRows = coverage.schemaVersion !== "1.0.0";
  const periodsMatch = base.observations.period === null ||
    (base.observations.period.start === coverage.period.start &&
      base.observations.period.end === coverage.period.end);
  if (!periodsMatch && !replaceRegistryCoverageRows) {
    return snapshot;
  }
  const sourceById = new Map<string, PublicSource>(
    base.sources.filter((source) => source.id !== "kozaru_numbered_openings")
      .map((source) => [source.id, source]),
  );
  for (const source of coverage.sources) {
    const current = sourceById.get(source.id);
    if (
      current !== undefined &&
      (!replaceRegistryCoverageRows ||
        current.name !== source.name ||
        current.kind !== source.kind ||
        current.access !== source.access ||
        current.url !== source.url)
    ) {
      return snapshot;
    }
    sourceById.set(source.id, source);
  }

  if (coverage.countries.length === 0 && !replaceRegistryCoverageRows) {
    return { ...base, sources: [...sourceById.values()] } satisfies PublicDashboardData;
  }

  // v2/v3 are the authoritative reviewed-evidence registry. If the main
  // snapshot still describes a narrower period, do not relabel or combine its
  // cells with the registry's historical range; rebuild this view from the
  // registry rows instead. Legacy v1 remains period-locked above.
  const compatibleBaseCells = periodsMatch ? base.mapCells : [];
  const countryByCode = new Map<string, CountryMapCell>(
    compatibleBaseCells.map((cell) => [cell.countryCode, cell]),
  );
  for (const row of coverage.countries) {
    countryByCode.set(
      row.countryCode,
      mergeCountry(
        countryByCode.get(row.countryCode),
        row,
        coverage.period,
        replaceRegistryCoverageRows,
      ),
    );
  }
  const mapCells = [...countryByCode.values()].sort(
    (left, right) =>
      left.countryName.localeCompare(right.countryName) ||
      left.countryCode.localeCompare(right.countryCode),
  );

  const compatibleBaseSets = periodsMatch ? base.sets : [];
  const setBySlug = new Map<string, SetMetric>(
    compatibleBaseSets.map((set) => [set.slug, set]),
  );
  for (const row of coverage.sets) {
    setBySlug.set(
      row.slug,
      mergeSet(setBySlug.get(row.slug), row, replaceRegistryCoverageRows),
    );
  }
  const sets = [...setBySlug.values()].sort(
    (left, right) =>
      right.releaseDate.localeCompare(left.releaseDate) || left.name.localeCompare(right.name),
  );

  const observedPacks = mapCells.reduce((total, cell) => total + cell.packsObserved, 0)
    + (unknownLocation?.packsObserved ?? 0);
  const completeOpenings = mapCells.reduce((total, cell) => total + cell.openings, 0)
    + (unknownLocation?.openings ?? 0);
  const sourceCountryContributions = mapCells.reduce(
    (total, cell) => total + cell.independentSources,
    0,
  );
  const countriesWithObservedRate = mapCells.filter(
    (cell) => cell.hitRate !== null,
  ).length;
  const countriesWithPublishedInference = mapCells.filter(
    (cell) =>
      cell.baselineRate !== null &&
      cell.posteriorMean !== null &&
      cell.credibleInterval !== null &&
      cell.deltaFromBaseline !== null,
  ).length;
  const asOf = mapCells.reduce<string | null>(
    (latest, cell) => laterTimestamp(latest, cell.updatedAt),
    unknownLocation?.updatedAt ?? null,
  );
  const regions = mapCells.map((cell) => ({
    slug: cell.countryCode.toLowerCase(),
    name: cell.countryName,
    countryCode: cell.countryCode,
    coverage: `${cell.packsObserved} observed packs from ${cell.independentSources} independent sources in the reviewed evidence range.`,
    packsObserved: cell.packsObserved,
    openings: cell.openings,
    independentSources: cell.independentSources,
    ...(cell.dataVersions === undefined ? {} : { dataVersions: cell.dataVersions }),
    ...(cell.collectionClass === undefined ? {} : { collectionClass: cell.collectionClass }),
    ...(cell.coverageAttributionBases === undefined
      ? {}
      : { coverageAttributionBases: cell.coverageAttributionBases }),
    ...(cell.ratePacksObserved === undefined
      ? {}
      : { ratePacksObserved: cell.ratePacksObserved }),
    ...(cell.qualifyingHitPacks === undefined
      ? {}
      : { qualifyingHitPacks: cell.qualifyingHitPacks }),
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
      aiValidatedSources: periodsMatch
        ? Math.min(base.summary.aiValidatedSources, completeOpenings)
        : 0,
      trackedSets: sets.length,
      trackedRegions: mapCells.length,
      baselineHitRate: countriesWithPublishedInference === 0
        ? null
        : base.summary.baselineHitRate,
      globalCoverage: `${mapCells.length} country or product-market coverage buckets have verified observations in the reviewed evidence range; ${countriesWithObservedRate} show an exact observed sample rate.`,
      methodologyVersion: "global-observation-v1",
    },
    observations: {
      ...base.observations,
      status: observedPacks === 0 ? "empty" : countriesWithObservedRate > 0 ? "published" : "collecting",
      period: observedPacks === 0 ? null : coverage.period,
      unknownLocation,
      observedPacks,
      completeOpenings,
      sourceCountryContributions,
      countriesObserved: mapCells.length,
      countriesWithPublishedRate: countriesWithObservedRate,
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
