import { z } from "zod";

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
  "insufficient",
]);
const productType = z.enum(["Booster Box", "ETB", "Booster Bundle"]);
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
    countryCode: z.literal("AU"),
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
  })
  .strict();
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

export const dashboardDataSchema = z
  .object({
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
        australiaCoverage: z.string().min(1).max(300),
        methodologyVersion: z.string().min(1).max(80),
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
    sets: z.array(setMetric).max(10_000),
    regions: z.array(regionMetric).max(10_000),
    retailers: z.array(retailerMetric).max(10_000),
    batches: z.array(batchMetric).max(10_000),
    trend: z.array(trendPoint).max(10_000),
    sources: z.array(source).max(1_000),
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

export const publicDashboardDataSchema = dashboardDataSchema
  .omit({ admin: true })
  .transform((data) => ({
    ...data,
    recentActivity: data.recentActivity.filter((activity) => activity.published),
  }));
