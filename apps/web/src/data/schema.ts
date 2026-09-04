import { z } from "zod";

import { isIsoAlpha2 } from "./iso-alpha2";

const probability = z.number().min(0).max(1);
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
const evidenceState = z.enum([
  "ready",
  "watch",
  "anomaly",
  "pending",
  "insufficient",
]);
const productType = z.enum(["Booster Box", "ETB", "Booster Bundle"]);
export const countryDataVersionsSchema = z
  .array(
    z
      .string()
      .min(1)
      .max(240)
      .refine((value) => value === value.trim(), "Data versions cannot have surrounding whitespace")
      .refine(
        (value) => Array.from(value).every((character) => {
          const codePoint = character.codePointAt(0) ?? 0;
          return codePoint >= 32 && codePoint !== 127;
        }),
        "Data versions cannot contain control characters",
      ),
  )
  .min(1)
  .max(32)
  .superRefine((versions, context) => {
    if (new Set(versions).size !== versions.length) {
      context.addIssue({
        code: z.ZodIssueCode.custom,
        message: "Data versions must be unique",
      });
    }
  });
const interval = z
  .object({ low: probability, high: probability })
  .strict()
  .refine(({ low, high }) => low <= high, "Interval low must not exceed high");

const observedMetric = z
  .object({
    packsObserved: z.number().int().nonnegative(),
    openings: z.number().int().nonnegative(),
    independentSources: z.number().int().nonnegative(),
    baselineRate: probability.nullable(),
    hitRate: probability.nullable(),
    posteriorMean: probability.nullable(),
    credibleInterval: interval.nullable(),
    deltaFromBaseline: z.number().min(-1).max(1).nullable(),
    state: evidenceState,
    sampleNote: z.string().min(1).max(500),
    updatedAt: isoDateTime,
  })
  .strict();

const validateObservedMetric = (
  value: z.infer<typeof observedMetric>,
  context: z.RefinementCtx,
) => {
  const addIssue = (message: string) =>
    context.addIssue({ code: z.ZodIssueCode.custom, message });
  if (value.openings > value.packsObserved) {
    addIssue("Openings cannot exceed observed packs");
  }
  if (value.independentSources > value.openings) {
    addIssue("Independent sources cannot exceed complete openings");
  }
  const insufficientEvidence =
    value.packsObserved < 30 || value.independentSources < 3;
  if (insufficientEvidence) {
    if (value.state !== "insufficient") {
      addIssue("Fewer than 30 observed packs or three sources must be Insufficient sample");
    }
    if (
      value.baselineRate !== null ||
      value.hitRate !== null ||
      value.posteriorMean !== null ||
      value.credibleInterval !== null ||
      value.deltaFromBaseline !== null
    ) {
      addIssue("Insufficient samples must withhold rate estimates");
    }
  } else if (value.state === "pending") {
    if (
      value.baselineRate !== null ||
      value.hitRate !== null ||
      value.posteriorMean !== null ||
      value.credibleInterval !== null ||
      value.deltaFromBaseline !== null
    ) {
      addIssue("Publication-pending samples must withhold every inference field");
    }
  } else {
    if (value.state === "insufficient") {
      addIssue("Sufficient packs and sources cannot be Insufficient sample");
    }
    if (
      value.baselineRate === null ||
      value.hitRate === null ||
      value.posteriorMean === null ||
      value.credibleInterval === null ||
      value.deltaFromBaseline === null
    ) {
      addIssue(
        "Published samples must include observed rate, posterior mean, interval, and baseline delta",
      );
    } else if (
      Math.abs(value.hitRate - value.baselineRate - value.deltaFromBaseline) > 1e-9
    ) {
      addIssue("Baseline delta must equal observed rate minus baseline rate");
    } else if (
      value.posteriorMean < value.credibleInterval.low ||
      value.posteriorMean > value.credibleInterval.high
    ) {
      addIssue("Posterior mean must be inside the credible interval");
    }
  }
  if (
    (value.state === "watch" || value.state === "anomaly") &&
    value.packsObserved < 200
  ) {
    addIssue("Watch and Possible anomaly require at least 200 observed packs");
  }
};

const setMetric = observedMetric
  .extend({
    slug: z.string().min(1).max(128),
    name: z.string().min(1).max(160),
    series: z.string().min(1).max(160),
    releaseDate: isoDate,
    signal: z.string().min(1).max(500),
  })
  .superRefine(validateObservedMetric);
const regionMetric = observedMetric
  .extend({
    slug: z.string().min(1).max(128),
    name: z.string().min(1).max(160),
    countryCode: z.string().refine(isIsoAlpha2, "Country code must be an official ISO alpha-2 code"),
    coverage: z.string().min(1).max(300),
  })
  .superRefine(validateObservedMetric);
const retailerMetric = observedMetric
  .extend({
    slug: z.string().min(1).max(128),
    name: z.string().min(1).max(160),
    region: z.string().min(1).max(160),
    channel: z.enum(["specialty", "mass-market", "online", "unknown"]),
  })
  .superRefine(validateObservedMetric);
const batchMetric = observedMetric
  .extend({
    code: z.string().min(1).max(128),
    setSlug: z.string().min(1).max(128),
    setName: z.string().min(1).max(160),
    region: z.string().min(1).max(160),
    productType,
    firstObserved: isoDate,
    lastObserved: isoDate,
  })
  .superRefine(validateObservedMetric);

const catalogSet = z
  .object({
    id: z.string().uuid(),
    slug: z.string().min(1).max(160).regex(/^[a-z0-9]+(?:-[a-z0-9]+)*$/),
    name: z.string().min(1).max(160),
    series: z.string().min(1).max(120).nullable(),
    releaseDate: isoDate.nullable(),
    language: z.literal("en"),
    current: z.literal(true),
    refreshedAt: isoDateTime,
  })
  .strict();

const catalogSnapshot = z
  .object({
    source: z.literal("tcgdex"),
    name: z.literal("TCGdex"),
    language: z.literal("en"),
    status: z.enum(["fresh", "stale", "attention", "unavailable"]),
    setCount: z.number().int().nonnegative().max(1_000_000),
    upstreamSetCount: z.number().int().nonnegative().max(1_000_000).nullable(),
    lastCheckedAt: isoDateTime.nullable(),
    lastChangedAt: isoDateTime.nullable(),
    revision: z.number().int().positive().nullable(),
    catalogOnly: z.literal(true),
    sets: z.array(catalogSet).max(1_000),
  })
  .strict()
  .superRefine((catalog, context) => {
    if (catalog.sets.length > catalog.setCount) {
      context.addIssue({
        code: z.ZodIssueCode.custom,
        message: "The bounded catalog array cannot exceed the full catalog count",
        path: ["sets"],
      });
    }
    if (new Set(catalog.sets.map((set) => set.id)).size !== catalog.sets.length) {
      context.addIssue({
        code: z.ZodIssueCode.custom,
        message: "Catalog set IDs must be unique",
        path: ["sets"],
      });
    }
    if (new Set(catalog.sets.map((set) => set.slug)).size !== catalog.sets.length) {
      context.addIssue({
        code: z.ZodIssueCode.custom,
        message: "Catalog set slugs must be unique",
        path: ["sets"],
      });
    }
    if (catalog.lastChangedAt !== null && catalog.lastCheckedAt !== null) {
      if (Date.parse(catalog.lastChangedAt) > Date.parse(catalog.lastCheckedAt)) {
        context.addIssue({
          code: z.ZodIssueCode.custom,
          message: "Catalog change time cannot follow its check time",
          path: ["lastChangedAt"],
        });
      }
    }
  });

const observationReadiness = z
  .object({
    status: z.enum(["empty", "collecting", "published"]),
    period: z.object({ start: isoDate, end: isoDate }).strict().nullable(),
    observedPacks: z.number().int().nonnegative(),
    completeOpenings: z.number().int().nonnegative(),
    independentSources: z.null(),
    sourceCountryContributions: z.number().int().nonnegative(),
    countriesObserved: z.number().int().min(0).max(249),
    countriesWithPublishedRate: z.number().int().min(0).max(249),
    asOf: isoDateTime.nullable(),
    methodologyVersion: z.string().min(1).max(120).nullable(),
    minimumPacks: z.literal(30),
    minimumSources: z.literal(3),
    watchMinimumPacks: z.literal(200),
    metricKey: z.literal("qualifying_hit_pack_rate"),
  })
  .strict()
  .superRefine((observations, context) => {
    if (observations.completeOpenings > observations.observedPacks) {
      context.addIssue({
        code: z.ZodIssueCode.custom,
        message: "Complete openings cannot exceed observed packs",
        path: ["completeOpenings"],
      });
    }
    if (observations.countriesWithPublishedRate > observations.countriesObserved) {
      context.addIssue({
        code: z.ZodIssueCode.custom,
        message: "Published countries cannot exceed observed countries",
        path: ["countriesWithPublishedRate"],
      });
    }
    if (
      observations.period !== null &&
      observations.period.start > observations.period.end
    ) {
      context.addIssue({
        code: z.ZodIssueCode.custom,
        message: "Observation period start cannot follow its end",
        path: ["period"],
      });
    }
  });

const countryMapCell = observedMetric
  .extend({
    countryCode: z.string().refine(isIsoAlpha2, "Country code must be an official ISO alpha-2 code"),
    countryName: z.string().min(1).max(160),
    dataVersions: countryDataVersionsSchema.optional(),
    periodStart: isoDate,
    periodEnd: isoDate,
    setScope: z.literal("all"),
    productScope: z.literal("all"),
    metricKey: z.literal("qualifying_hit_pack_rate"),
    metricVersion: z.string().min(1).max(80).regex(/^[a-z0-9][a-z0-9._-]*$/),
    methodologyVersion: z.string().min(1).max(120),
    packsObserved: z.number().int().positive(),
    openings: z.number().int().positive(),
    independentSources: z.number().int().positive(),
  })
  .superRefine((cell, context) => {
    validateObservedMetric(cell, context);
    if (cell.periodStart > cell.periodEnd) {
      context.addIssue({
        code: z.ZodIssueCode.custom,
        message: "Map-cell period start cannot follow its end",
        path: ["periodStart"],
      });
    }
  });

const trendPoint = z
  .object({
    date: isoDate,
    observedRate: probability.nullable(),
    baselineRate: probability.nullable(),
    packsObserved: z.number().int().nonnegative(),
    completeOpenings: z.number().int().nonnegative(),
    independentSources: z.number().int().nonnegative(),
  })
  .strict()
  .superRefine((point, context) => {
    const addIssue = (message: string, path: string) =>
      context.addIssue({ code: z.ZodIssueCode.custom, message, path: [path] });
    if (point.completeOpenings > point.packsObserved) {
      addIssue("Complete openings cannot exceed observed packs", "completeOpenings");
    }
    if (point.independentSources > point.completeOpenings) {
      addIssue("Independent sources cannot exceed complete openings", "independentSources");
    }
    const insufficient = point.packsObserved < 30 || point.independentSources < 3;
    if (insufficient && (point.observedRate !== null || point.baselineRate !== null)) {
      addIssue("Insufficient trend evidence must withhold both rates", "observedRate");
    }
    if (!insufficient && (point.observedRate === null || point.baselineRate === null)) {
      addIssue("Sufficient trend evidence must publish both rates", "observedRate");
    }
  });
const sourceCoverage = z
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

const source = z
  .object({
    id: z.string().min(1).max(128),
    name: z.string().min(1).max(160),
    kind: z.enum(["catalog", "video", "community", "social"]),
    access: z.enum(["public", "api-key", "browser-auth-required"]),
    status: z.enum(["operational", "delayed", "attention", "paused"]),
    lastCollectedAt: isoDateTime.nullable(),
    url: publicHttpUrl,
    note: z.string().min(1).max(500),
    coverage: sourceCoverage.optional(),
  })
  .strict()
  .superRefine((source, context) => {
    if (
      source.coverage !== undefined &&
      (source.kind !== "community" || source.access !== "public")
    ) {
      context.addIssue({
        code: z.ZodIssueCode.custom,
        message: "Only public community sources can carry reviewed coverage",
        path: ["coverage"],
      });
    }
  });

const socialPulseSourceBase = {
  kind: z.literal("social"),
  access: z.literal("public"),
  status: z.enum(["operational", "delayed", "attention", "paused"]),
  freshness: z.enum(["fresh", "delayed", "attention", "paused"]),
  lastCollectedAt: isoDateTime.nullable(),
  newCandidates24h: z.number().int().nonnegative().max(1_000_000),
  retainedCandidates: z.number().int().nonnegative().max(1_000_000),
  activityOnly: z.literal(true),
  statisticsEligible: z.literal(false),
} as const;

const socialPulseSource = <
  TId extends string,
  TName extends string,
>(id: TId, name: TName) =>
  z
    .object({
      id: z.literal(id),
      name: z.literal(name),
      ...socialPulseSourceBase,
    })
    .strict();

const socialActivityPulseSourceSchemas = [
  socialPulseSource("bluesky_jetstream", "Bluesky Jetstream discovery"),
  socialPulseSource("nostr_multi_relay", "Nostr multi-relay discovery"),
  socialPulseSource("mastodon_public_hashtag", "Mastodon public hashtag discovery"),
] as const;

const socialActivityPulseWindow = z
  .object({
    start: isoDateTime,
    end: isoDateTime,
  })
  .strict()
  .superRefine((window, context) => {
    if (Date.parse(window.end) - Date.parse(window.start) !== 24 * 60 * 60 * 1000) {
      context.addIssue({
        code: z.ZodIssueCode.custom,
        message: "Social activity pulse window must cover exactly 24 hours",
        path: ["start"],
      });
    }
  });

export const publicSocialDiscoveryV4Schema = z
  .object({
    schemaVersion: z.literal("4.0.0"),
    window: socialActivityPulseWindow,
    activityOnly: z.literal(true),
    nonEvidence: z.literal(true),
    sources: z.tuple([...socialActivityPulseSourceSchemas]),
  })
  .strict()
  .superRefine((pulse, context) => {
    for (const [index, source] of pulse.sources.entries()) {
      const expectedFreshness = source.status === "operational"
        ? "fresh"
        : source.status;
      if (source.freshness !== expectedFreshness) {
        context.addIssue({
          code: z.ZodIssueCode.custom,
          message: "Freshness must agree with the source status",
          path: ["sources", index, "freshness"],
        });
      }
    }
  });
const service = z
  .object({
    id: z.string().min(1).max(128),
    name: z.string().min(1).max(160),
    status: z.enum(["operational", "degraded", "maintenance"]),
    detail: z.string().min(1).max(500),
    checkedAt: isoDateTime,
  })
  .strict();
const job = z
  .object({
    id: z.string().min(1).max(128),
    name: z.string().min(1).max(160),
    status: z.enum(["running", "queued", "succeeded", "failed"]),
    lastRunAt: isoDateTime.nullable(),
    nextRunAt: isoDateTime.nullable(),
    records: z.number().int().nonnegative(),
  })
  .strict();
const browserSession = z
  .object({
    id: z.string().min(1).max(128),
    source: z.string().min(1).max(160),
    status: z.enum(["ready", "auth-required", "expired"]),
    profile: z.string().min(1).max(160),
    lastVerifiedAt: isoDateTime.nullable(),
  })
  .strict();
const aiUsage = z
  .object({
    day: isoDate,
    stage: z.enum(["extract", "validate", "escalate"]),
    requests: z.number().int().nonnegative(),
    inputTokens: z.number().int().nonnegative(),
    outputTokens: z.number().int().nonnegative(),
    estimatedAud: z.number().nonnegative(),
  })
  .strict();
const systemCheck = z
  .object({
    id: z.string().min(1).max(128),
    name: z.string().min(1).max(160),
    status: z.enum(["ok", "warning", "error"]),
    value: z.string().min(1).max(160),
    detail: z.string().min(1).max(500),
  })
  .strict();

const recentActivity = z
  .object({
    id: z.string().min(1).max(128),
    observedAt: isoDateTime,
    platform: z.string().min(1).max(160),
    setName: z.string().min(1).max(160),
    productType,
    packCount: z.number().int().positive(),
    region: z.string().min(1).max(160),
    retailer: z.string().min(1).max(160),
    evidenceTier: z.enum(["A", "B", "activity-only"]),
    classification: z.enum(["rate-eligible", "activity-only"]),
    statisticsEligible: z.boolean(),
    published: z.boolean(),
    sourceUrl: publicHttpUrl,
  })
  .strict();

const dashboardDataObject = z
  .object({
    schemaVersion: z.literal("2.0.0"),
    mode: z.enum(["demo", "live"]),
    generatedAt: isoDateTime,
    summary: z
      .object({
        observedPacks: z.number().int().nonnegative(),
        completeOpenings: z.number().int().nonnegative(),
        aiValidatedSources: z.number().int().nonnegative(),
        trackedSets: z.number().int().nonnegative(),
        trackedRegions: z.number().int().nonnegative(),
        batchSightings: z.number().int().nonnegative(),
        baselineHitRate: probability.nullable(),
        globalCoverage: z.string().min(1).max(300),
        methodologyVersion: z.string().min(1).max(120),
      })
      .strict()
      .superRefine((summary, context) => {
        if (summary.completeOpenings > summary.observedPacks) {
          context.addIssue({
            code: "custom",
            message: "Complete openings cannot exceed observed packs",
            path: ["completeOpenings"],
          });
        }
        if (summary.aiValidatedSources > summary.completeOpenings) {
          context.addIssue({
            code: "custom",
            message: "AI-validated sources cannot exceed complete openings",
            path: ["aiValidatedSources"],
          });
        }
        if (
          (summary.observedPacks < 30 || summary.aiValidatedSources < 3) &&
          summary.baselineHitRate !== null
        ) {
          context.addIssue({
            code: "custom",
            message: "Insufficient dashboard evidence must withhold the baseline rate",
            path: ["baselineHitRate"],
          });
        }
      }),
    catalog: catalogSnapshot,
    observations: observationReadiness,
    mapCells: z.array(countryMapCell).max(249),
    sets: z.array(setMetric).max(10_000),
    regions: z.array(regionMetric).max(10_000),
    retailers: z.array(retailerMetric).max(10_000),
    batches: z.array(batchMetric).max(10_000),
    trend: z.array(trendPoint).max(10_000),
    sources: z.array(source).max(1_000),
    socialActivityPulse: publicSocialDiscoveryV4Schema.optional(),
    services: z.array(service).max(1_000),
    recentActivity: z.array(recentActivity).max(10_000),
    admin: z
      .object({
        jobs: z.array(job).max(10_000),
        browserSessions: z.array(browserSession).max(1_000),
        aiUsage: z.array(aiUsage).max(10_000),
        system: z.array(systemCheck).max(1_000),
      })
      .strict(),
  })
  .strict();

type GlobalSnapshotValue = Pick<
  z.infer<typeof dashboardDataObject>,
  "catalog" | "mapCells" | "observations" | "summary"
>;

function validateGlobalSnapshot(
  value: GlobalSnapshotValue,
  context: z.RefinementCtx,
) {
  const { mapCells, observations, summary } = value;
  const addIssue = (message: string, path: readonly PropertyKey[]) =>
    context.addIssue({
      code: z.ZodIssueCode.custom,
      message,
      path: [...path] as (string | number)[],
    });

  if (new Set(mapCells.map((cell) => cell.countryCode)).size !== mapCells.length) {
    addIssue("Map cells must contain unique country codes", ["mapCells"]);
  }

  const publishedCount = mapCells.filter((cell) => cell.hitRate !== null).length;
  const packs = mapCells.reduce((total, cell) => total + cell.packsObserved, 0);
  const openings = mapCells.reduce((total, cell) => total + cell.openings, 0);
  const sourceContributions = mapCells.reduce(
    (total, cell) => total + cell.independentSources,
    0,
  );

  if (observations.countriesObserved !== mapCells.length) {
    addIssue("Observed-country count must equal the map-cell count", ["observations", "countriesObserved"]);
  }
  if (observations.countriesWithPublishedRate !== publishedCount) {
    addIssue("Published-country count must equal cells with a public rate", ["observations", "countriesWithPublishedRate"]);
  }
  if (observations.observedPacks !== packs) {
    addIssue("Observation pack total must equal the selected map period", ["observations", "observedPacks"]);
  }
  if (observations.completeOpenings !== openings) {
    addIssue("Observation opening total must equal the selected map period", ["observations", "completeOpenings"]);
  }
  if (observations.sourceCountryContributions !== sourceContributions) {
    addIssue("Source-country contributions must equal the per-country sum", ["observations", "sourceCountryContributions"]);
  }
  if (
    summary.observedPacks !== packs ||
    summary.completeOpenings !== openings ||
    summary.trackedRegions !== mapCells.length
  ) {
    addIssue("Legacy summary totals must describe the same global map period", ["summary"]);
  }

  const expectedStatus = mapCells.length === 0
    ? "empty"
    : publishedCount === 0
      ? "collecting"
      : "published";
  if (observations.status !== expectedStatus) {
    addIssue("Observation status must match the map publication state", ["observations", "status"]);
  }

  if (mapCells.length === 0) {
    if (observations.period !== null || observations.asOf !== null) {
      addIssue("An empty observation state cannot fabricate a period or as-of time", ["observations"]);
    }
    return;
  }

  if (observations.period === null || observations.asOf === null) {
    addIssue("Observed map cells require a shared period and as-of time", ["observations"]);
    return;
  }
  for (const cell of mapCells) {
    if (
      cell.periodStart !== observations.period.start ||
      cell.periodEnd !== observations.period.end
    ) {
      addIssue("Every map cell must use the one selected observation period", ["mapCells"]);
      break;
    }
  }
}

export const dashboardDataSchema = dashboardDataObject.superRefine(validateGlobalSnapshot);

export const publicDashboardDataSchema = dashboardDataObject
  .omit({ admin: true })
  .superRefine(validateGlobalSnapshot)
  .transform((data) => ({
    ...data,
    recentActivity: data.recentActivity.filter((activity) => activity.published),
  }));
