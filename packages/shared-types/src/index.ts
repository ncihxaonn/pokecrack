import { z } from "zod";

export const PUBLIC_OBSERVATION_STATUSES = [
  "accepted",
  "activity_only",
  "rejected",
] as const;

export const EVIDENCE_TIERS = ["A", "B", "C", "D"] as const;

export const SIGNAL_LABELS = [
  "Insufficient sample",
  "No significant signal",
  "Watch",
  "Possible anomaly",
] as const;

export const publicObservationStatusSchema = z.enum(PUBLIC_OBSERVATION_STATUSES);
export const evidenceTierSchema = z.enum(EVIDENCE_TIERS);
export const STATISTICAL_EVIDENCE_TIERS = ["A", "B"] as const;
export const statisticalEvidenceTierSchema = z.enum(STATISTICAL_EVIDENCE_TIERS);
export const signalLabelSchema = z.enum(SIGNAL_LABELS);

export const PUBLISHED_OBSERVATION_STATUSES = [
  "accepted",
  "activity_only",
] as const;
export const publishedObservationStatusSchema = z.enum(
  PUBLISHED_OBSERVATION_STATUSES,
);

export const PRODUCT_TYPES = [
  "booster_box",
  "etb",
  "booster_bundle",
  "other",
  "unknown",
] as const;

export const COLLECTOR_ROUTES = [
  "official_api",
  "scrapling_http",
  "scrapling_dynamic",
  "opencli_authenticated",
  "manual_import",
  "disabled",
] as const;

export const productTypeSchema = z.enum(PRODUCT_TYPES);
export const collectorRouteSchema = z.enum(COLLECTOR_ROUTES);

export type PublicObservationStatus = z.infer<typeof publicObservationStatusSchema>;
export type EvidenceTier = z.infer<typeof evidenceTierSchema>;
export type SignalLabel = z.infer<typeof signalLabelSchema>;
export type ProductType = z.infer<typeof productTypeSchema>;
export type CollectorRoute = z.infer<typeof collectorRouteSchema>;


export const PUBLIC_SOURCE_KINDS = [
  "official_api",
  "public_web",
  "authenticated_social",
  "fixture",
  "manual_import",
] as const;

export const publicIdSchema = z
  .string()
  .min(1)
  .max(128)
  .regex(/^[A-Za-z0-9][A-Za-z0-9._:-]*$/);
const nonNegativeCountSchema = z.number().int().min(0).max(1_000_000);

export const publicOpeningObservationSchema = z
  .object({
    id: publicIdSchema,
    setCode: z.string().min(1).max(40),
    productName: z.string().min(1).max(160),
    productType: productTypeSchema,
    openedAt: z.string().datetime({ offset: true }),
    packCount: z.number().int().min(1).max(100_000),
    hitCount: nonNegativeCountSchema,
    rarityCounts: z.record(
      z.string().regex(/^[a-z][a-z0-9_]*$/),
      nonNegativeCountSchema,
    ),
    countryCode: z.string().regex(/^[A-Z]{2}$/).optional(),
    region: z.string().min(1).max(80).optional(),
    evidenceTier: evidenceTierSchema,
    status: publishedObservationStatusSchema,
    sourceKind: z.enum(PUBLIC_SOURCE_KINDS),
    isFixture: z.boolean(),
  })
  .strict()
  .superRefine((observation, context) => {
    if ((observation.sourceKind === "fixture") !== observation.isFixture) {
      context.addIssue({
        code: "custom",
        message: "fixture source and marker must agree",
        path: ["isFixture"],
      });
    }
  });

export type PublicOpeningObservation = z.infer<
  typeof publicOpeningObservationSchema
>;
export type PublicSourceKind = (typeof PUBLIC_SOURCE_KINDS)[number];

export const probabilitySchema = z.number().finite().min(0).max(1);
export const publicSlugSchema = z
  .string()
  .min(1)
  .max(128)
  .regex(/^[a-z0-9]+(?:-[a-z0-9]+)*$/);
export const countryCodeSchema = z.string().regex(/^[A-Z]{2}$/);
export const isoDateTimeSchema = z.string().datetime({ offset: true });
export const isoDateSchema = z
  .string()
  .regex(/^\d{4}-\d{2}-\d{2}$/)
  .refine((value) => {
    const date = new Date(`${value}T00:00:00.000Z`);
    return (
      !Number.isNaN(date.getTime()) &&
      date.toISOString().slice(0, 10) === value
    );
  }, "invalid calendar date");

export const publicCredibleIntervalSchema = z
  .object({
    low: probabilitySchema,
    high: probabilitySchema,
    level: z.literal(0.9),
  })
  .strict()
  .superRefine((interval, context) => {
    if (interval.low > interval.high) {
      context.addIssue({
        code: "custom",
        message: "low must not exceed high",
        path: ["low"],
      });
    }
  });

const publicMetricShape = {
  packsObserved: z.number().int().min(0).max(100_000_000),
  openings: z.number().int().min(0).max(10_000_000),
  independentSources: z.number().int().min(0).max(1_000_000),
  baselineRate: probabilitySchema.nullable(),
  hitRate: probabilitySchema.nullable(),
  posteriorMean: probabilitySchema.nullable(),
  credibleInterval: publicCredibleIntervalSchema.nullable(),
  deltaFromBaseline: z.number().finite().min(-1).max(1).nullable(),
  signalLabel: signalLabelSchema,
  updatedAt: isoDateTimeSchema,
  isFixture: z.boolean(),
} as const;

type PublicMetricInput = {
  packsObserved: number;
  openings: number;
  independentSources: number;
  baselineRate: number | null;
  hitRate: number | null;
  posteriorMean: number | null;
  credibleInterval: { low: number; high: number; level: 0.9 } | null;
  deltaFromBaseline: number | null;
  signalLabel: SignalLabel;
};

const validatePublicMetric = (
  metric: PublicMetricInput,
  context: z.RefinementCtx,
): void => {
  if (metric.openings > metric.packsObserved) {
    context.addIssue({
      code: "custom",
      message: "openings must not exceed packsObserved",
      path: ["openings"],
    });
  }
  if (metric.independentSources > metric.openings) {
    context.addIssue({
      code: "custom",
      message: "independentSources must not exceed openings",
      path: ["independentSources"],
    });
  }

  const insufficientEvidence =
    metric.packsObserved < 30 || metric.independentSources < 3;
  if (insufficientEvidence) {
    if (metric.signalLabel !== "Insufficient sample") {
      context.addIssue({
        code: "custom",
        message: "fewer than 30 packs or three sources require Insufficient sample",
        path: ["signalLabel"],
      });
    }
  } else if (metric.signalLabel === "Insufficient sample") {
    context.addIssue({
      code: "custom",
      message: "sufficient packs and sources cannot be Insufficient sample",
      path: ["signalLabel"],
    });
  }

  if (
    (metric.signalLabel === "Watch" || metric.signalLabel === "Possible anomaly") &&
    metric.packsObserved < 200
  ) {
    context.addIssue({
      code: "custom",
      message: "Watch and Possible anomaly require at least 200 observed packs",
      path: ["signalLabel"],
    });
  }

  if (metric.hitRate === null) {
    if (
      metric.baselineRate !== null ||
      metric.posteriorMean !== null ||
      metric.credibleInterval !== null ||
      metric.deltaFromBaseline !== null
    ) {
      context.addIssue({
        code: "custom",
        message: "unpublished rates cannot include interval or delta values",
        path: ["hitRate"],
      });
    }
    if (metric.signalLabel !== "Insufficient sample") {
      context.addIssue({
        code: "custom",
        message: "unpublished rates require Insufficient sample",
        path: ["signalLabel"],
      });
    }
    return;
  }

  if (metric.signalLabel === "Insufficient sample") {
    context.addIssue({
      code: "custom",
      message: "Insufficient sample cannot publish a rate",
      path: ["signalLabel"],
    });
  }

  if (metric.baselineRate === null) {
    context.addIssue({
      code: "custom",
      message: "published rates require baselineRate",
      path: ["baselineRate"],
    });
  } else if (metric.deltaFromBaseline === null) {
    context.addIssue({
      code: "custom",
      message: "published rates require deltaFromBaseline",
      path: ["deltaFromBaseline"],
    });
  } else if (
    Math.abs(metric.hitRate - metric.baselineRate - metric.deltaFromBaseline) > 1e-9
  ) {
    context.addIssue({
      code: "custom",
      message: "deltaFromBaseline must equal hitRate minus baselineRate",
      path: ["deltaFromBaseline"],
    });
  }

  if (metric.posteriorMean === null) {
    context.addIssue({
      code: "custom",
      message: "published rates require a posterior mean",
      path: ["posteriorMean"],
    });
    return;
  }

  if (metric.credibleInterval === null) {
    context.addIssue({
      code: "custom",
      message: "published rates require a credible interval",
      path: ["credibleInterval"],
    });
    return;
  }

  const centralEstimate = metric.posteriorMean;
  if (
    centralEstimate < metric.credibleInterval.low ||
    centralEstimate > metric.credibleInterval.high
  ) {
    context.addIssue({
      code: "custom",
      message: "posteriorMean must be inside the credible interval",
      path: ["posteriorMean"],
    });
  }
};

export const publicSetSummarySchema = z
  .object({
    id: publicIdSchema,
    slug: publicSlugSchema,
    name: z.string().trim().min(1).max(160),
    series: z.string().trim().min(1).max(160),
    releaseDate: isoDateSchema,
    ...publicMetricShape,
  })
  .strict()
  .superRefine(validatePublicMetric);

export const publicRegionSummarySchema = z
  .object({
    id: publicIdSchema,
    slug: publicSlugSchema,
    name: z.string().trim().min(1).max(160),
    countryCode: z.literal("AU"),
    coverage: z.string().trim().min(1).max(240),
    ...publicMetricShape,
  })
  .strict()
  .superRefine(validatePublicMetric);

export const RETAILER_CHANNELS = [
  "specialty",
  "mass_market",
  "online",
  "unknown",
] as const;
export const retailerChannelSchema = z.enum(RETAILER_CHANNELS);

export const publicRetailerSummarySchema = z
  .object({
    id: publicIdSchema,
    slug: publicSlugSchema,
    name: z.string().trim().min(1).max(160),
    region: z.string().trim().min(1).max(160),
    channel: retailerChannelSchema,
    ...publicMetricShape,
  })
  .strict()
  .superRefine(validatePublicMetric);

export const publicBatchSummarySchema = z
  .object({
    id: publicIdSchema,
    code: z.string().trim().min(1).max(128),
    setId: publicIdSchema,
    setName: z.string().trim().min(1).max(160),
    region: z.string().trim().min(1).max(160),
    firstObservedAt: isoDateTimeSchema,
    lastObservedAt: isoDateTimeSchema,
    ...publicMetricShape,
  })
  .strict()
  .superRefine((batch, context) => {
    validatePublicMetric(batch, context);
    if (Date.parse(batch.firstObservedAt) > Date.parse(batch.lastObservedAt)) {
      context.addIssue({
        code: "custom",
        message: "firstObservedAt must not be after lastObservedAt",
        path: ["firstObservedAt"],
      });
    }
  });

export type PublicCredibleInterval = z.infer<typeof publicCredibleIntervalSchema>;
export type PublicSetSummary = z.infer<typeof publicSetSummarySchema>;
export type PublicRegionSummary = z.infer<typeof publicRegionSummarySchema>;
export type PublicRetailerSummary = z.infer<typeof publicRetailerSummarySchema>;
export type PublicBatchSummary = z.infer<typeof publicBatchSummarySchema>;
export type RetailerChannel = z.infer<typeof retailerChannelSchema>;

export const httpUrlSchema = z
  .string()
  .max(2_048)
  .refine((value) => {
    try {
      const protocol = new URL(value).protocol;
      return protocol === "http:" || protocol === "https:";
    } catch {
      return false;
    }
  }, "URL must be a valid http or https URL");

const hostnameSchema = z
  .string()
  .min(1)
  .max(253)
  .regex(
    /^(?:[a-z0-9](?:[a-z0-9-]{0,61}[a-z0-9])?\.)*[a-z0-9](?:[a-z0-9-]{0,61}[a-z0-9])?$/i,
  );
const sha256Schema = z.string().regex(/^[a-f0-9]{64}$/);
const sensitiveMetadataKeyPattern =
  /(?:cookie|token|authorization|password|secret|browser[_-]?profile|job[_-]?payload|raw[_-]?ai)/i;

const validateSafeJson = (
  value: unknown,
  context: z.RefinementCtx,
  path: PropertyKey[] = [],
  depth = 0,
): void => {
  if (depth > 6) {
    context.addIssue({
      code: "custom",
      message: "metadata exceeds the maximum nesting depth",
      path,
    });
    return;
  }
  if (
    value === null ||
    typeof value === "string" ||
    typeof value === "boolean" ||
    (typeof value === "number" && Number.isFinite(value))
  ) {
    return;
  }
  if (Array.isArray(value)) {
    if (value.length > 100) {
      context.addIssue({
        code: "custom",
        message: "metadata arrays are limited to 100 entries",
        path,
      });
      return;
    }
    value.forEach((item, index) => {
      validateSafeJson(item, context, [...path, index], depth + 1);
    });
    return;
  }
  if (typeof value === "object") {
    const prototype = Object.getPrototypeOf(value);
    if (prototype !== Object.prototype && prototype !== null) {
      context.addIssue({
        code: "custom",
        message: "metadata must contain plain JSON values",
        path,
      });
      return;
    }
    const entries = Object.entries(value as Record<string, unknown>);
    if (entries.length > 100) {
      context.addIssue({
        code: "custom",
        message: "metadata objects are limited to 100 keys",
        path,
      });
      return;
    }
    for (const [key, item] of entries) {
      if (sensitiveMetadataKeyPattern.test(key)) {
        context.addIssue({
          code: "custom",
          message: "sensitive metadata keys are forbidden",
          path: [...path, key],
        });
      } else {
        validateSafeJson(item, context, [...path, key], depth + 1);
      }
    }
    return;
  }
  context.addIssue({
    code: "custom",
    message: "metadata must contain JSON values",
    path,
  });
};

export const safeCollectorMetadataSchema = z
  .record(z.string().min(1).max(128), z.unknown())
  .superRefine((value, context) => {
    validateSafeJson(value, context);
  });

export const sourceItemCandidateSchema = z
  .object({
    source_url: httpUrlSchema,
    canonical_url: httpUrlSchema.nullable(),
    source_domain: hostnameSchema.nullable(),
    collector: collectorRouteSchema,
    platform: z.string().trim().min(1).max(64).nullable(),
    platform_id: z.string().trim().min(1).max(256).nullable(),
    title: z.string().trim().min(1).max(500).nullable(),
    excerpt: z.string().trim().min(1).max(4_000).nullable(),
    content: z.string().min(1).max(250_000).nullable(),
    content_sha256: sha256Schema.nullable(),
    author: z.string().trim().min(1).max(256).nullable(),
    published_at: isoDateTimeSchema.nullable(),
    collected_at: isoDateTimeSchema,
    metadata: safeCollectorMetadataSchema,
    image_urls: z.array(httpUrlSchema).max(32),
  })
  .strict()
  .superRefine((candidate, context) => {
    if (
      candidate.published_at !== null &&
      Date.parse(candidate.published_at) > Date.parse(candidate.collected_at)
    ) {
      context.addIssue({
        code: "custom",
        message: "published_at must not be after collected_at",
        path: ["published_at"],
      });
    }
  });

export const EXTRACTOR_EVIDENCE_FIELDS = [
  "set_name",
  "product_name",
  "product_type",
  "pack_count",
  "hits",
  "country_code",
  "region",
  "retailer",
  "batch_code",
  "opened_at",
  "evidence_tier",
] as const;
export const extractorEvidenceFieldSchema = z.enum(EXTRACTOR_EVIDENCE_FIELDS);

export const extractedHitSchema = z
  .object({
    card_name: z.string().trim().min(1).max(300),
    collector_number: z.string().trim().min(1).max(64).nullable(),
    rarity_label: z.string().trim().min(1).max(128).nullable(),
    quantity: z.number().int().min(1).max(1_000),
  })
  .strict();

export const evidenceQuoteSchema = z
  .object({
    field: extractorEvidenceFieldSchema,
    quote: z.string().trim().min(1).max(2_000),
    source_locator: z.string().trim().min(1).max(256).nullable(),
  })
  .strict();

const nullableExtractedTextSchema = z.string().trim().min(1).max(300).nullable();

export const extractorOutputSchema = z
  .object({
    set_name: nullableExtractedTextSchema,
    product_name: nullableExtractedTextSchema,
    product_type: productTypeSchema,
    pack_count: z.number().int().min(0).max(10_000).nullable(),
    hits: z.array(extractedHitSchema).max(10_000),
    country_code: countryCodeSchema.nullable(),
    region: nullableExtractedTextSchema,
    retailer: nullableExtractedTextSchema,
    batch_code: z.string().trim().min(1).max(128).nullable(),
    opened_at: isoDateTimeSchema.nullable(),
    evidence_tier: evidenceTierSchema,
    confidence: probabilitySchema,
    evidence: z.array(evidenceQuoteSchema).max(100),
  })
  .strict();

export const VALIDATION_VERDICTS = [
  "accept",
  "activity_only",
  "reject",
] as const;
export const validationVerdictSchema = z.enum(VALIDATION_VERDICTS);

export const validatedHitSchema = z
  .object({
    card_id: publicIdSchema.nullable(),
    card_name: z.string().trim().min(1).max(300),
    collector_number: z.string().trim().min(1).max(64).nullable(),
    rarity_key: z
      .string()
      .regex(/^[a-z][a-z0-9_]{0,63}$/)
      .nullable(),
    quantity: z.number().int().min(1).max(1_000),
  })
  .strict();

export const validatorOutputSchema = z
  .object({
    decision: validationVerdictSchema,
    set_id: publicIdSchema.nullable(),
    set_name: nullableExtractedTextSchema,
    product_name: nullableExtractedTextSchema,
    product_type: productTypeSchema,
    pack_count: z.number().int().min(0).max(10_000).nullable(),
    hits: z.array(validatedHitSchema).max(10_000),
    country_code: countryCodeSchema.nullable(),
    region: nullableExtractedTextSchema,
    retailer: nullableExtractedTextSchema,
    batch_code: z.string().trim().min(1).max(128).nullable(),
    opened_at: isoDateTimeSchema.nullable(),
    evidence_tier: evidenceTierSchema,
    confidence: probabilitySchema,
    conflict_codes: z
      .array(z.string().regex(/^[a-z][a-z0-9_]{0,63}$/))
      .max(100),
  })
  .strict();

export type SourceItemCandidate = z.infer<typeof sourceItemCandidateSchema>;
export type ExtractorEvidenceField = z.infer<typeof extractorEvidenceFieldSchema>;
export type ExtractedHit = z.infer<typeof extractedHitSchema>;
export type EvidenceQuote = z.infer<typeof evidenceQuoteSchema>;
export type ExtractorOutput = z.infer<typeof extractorOutputSchema>;
export type ValidationVerdict = z.infer<typeof validationVerdictSchema>;
export type ValidatedHit = z.infer<typeof validatedHitSchema>;
export type ValidatorOutput = z.infer<typeof validatorOutputSchema>;

export const PUBLIC_ACTIVITY_KINDS = [
  "opening",
  "sighting",
  "batch_mention",
] as const;
export const PUBLIC_ACTIVITY_SUBJECT_KINDS = [
  "set",
  "product",
  "region",
  "retailer",
  "batch",
] as const;
export const publicActivityKindSchema = z.enum(PUBLIC_ACTIVITY_KINDS);
export const publicActivitySubjectKindSchema = z.enum(PUBLIC_ACTIVITY_SUBJECT_KINDS);

const publicActivitySubjectSchema = z
  .object({
    kind: publicActivitySubjectKindSchema,
    id: publicIdSchema,
    label: z.string().trim().min(1).max(160),
  })
  .strict();

export const publicRecentActivityItemSchema = z
  .object({
    id: publicIdSchema,
    kind: publicActivityKindSchema,
    subject: publicActivitySubjectSchema,
    occurredAt: isoDateTimeSchema,
    observedAt: isoDateTimeSchema,
    packCount: z.number().int().min(1).max(100_000).nullable(),
    productType: productTypeSchema.nullable(),
    evidenceTier: evidenceTierSchema,
    status: publishedObservationStatusSchema,
    countryCode: z.literal("AU"),
    region: z.string().trim().min(1).max(160),
    statisticsEligible: z.boolean(),
    isFixture: z.boolean(),
  })
  .strict()
  .superRefine((activity, context) => {
    if (Date.parse(activity.observedAt) < Date.parse(activity.occurredAt)) {
      context.addIssue({
        code: "custom",
        message: "observedAt must not precede occurredAt",
        path: ["observedAt"],
      });
    }
    if (activity.kind === "opening" && activity.packCount === null) {
      context.addIssue({
        code: "custom",
        message: "opening activity requires packCount",
        path: ["packCount"],
      });
    }
    if (
      activity.statisticsEligible &&
      (activity.kind !== "opening" ||
        activity.status !== "accepted" ||
        !["A", "B"].includes(activity.evidenceTier) ||
        activity.packCount === null)
    ) {
      context.addIssue({
        code: "custom",
        message: "statistics eligibility requires an accepted tier A/B opening",
        path: ["statisticsEligible"],
      });
    }
    if (activity.status === "activity_only" && activity.statisticsEligible) {
      context.addIssue({
        code: "custom",
        message: "activity_only evidence cannot be statistics eligible",
        path: ["statisticsEligible"],
      });
    }
  });

export const FRESHNESS_STATUSES = [
  "fresh",
  "delayed",
  "stale",
  "unavailable",
] as const;
export const freshnessStatusValueSchema = z.enum(FRESHNESS_STATUSES);

export const publicFreshnessStatusSchema = z
  .object({
    status: freshnessStatusValueSchema,
    asOf: isoDateTimeSchema,
    lastSuccessfulCollectionAt: isoDateTimeSchema.nullable(),
    ageSeconds: z.number().int().min(0).max(31_536_000).nullable(),
    nextExpectedAt: isoDateTimeSchema.nullable(),
  })
  .strict()
  .superRefine((freshness, context) => {
    const unavailable = freshness.status === "unavailable";
    if (unavailable) {
      if (
        freshness.lastSuccessfulCollectionAt !== null ||
        freshness.ageSeconds !== null ||
        freshness.nextExpectedAt !== null
      ) {
        context.addIssue({
          code: "custom",
          message: "unavailable freshness cannot expose collection timing",
          path: ["status"],
        });
      }
      return;
    }

    if (
      freshness.lastSuccessfulCollectionAt === null ||
      freshness.ageSeconds === null
    ) {
      context.addIssue({
        code: "custom",
        message: "available freshness requires collection age",
        path: ["lastSuccessfulCollectionAt"],
      });
      return;
    }

    const asOf = Date.parse(freshness.asOf);
    const lastSuccess = Date.parse(freshness.lastSuccessfulCollectionAt);
    if (lastSuccess > asOf) {
      context.addIssue({
        code: "custom",
        message: "lastSuccessfulCollectionAt must not be in the future",
        path: ["lastSuccessfulCollectionAt"],
      });
    }
    if (Math.floor((asOf - lastSuccess) / 1_000) !== freshness.ageSeconds) {
      context.addIssue({
        code: "custom",
        message: "ageSeconds must match the collection timestamp",
        path: ["ageSeconds"],
      });
    }
    if (
      freshness.nextExpectedAt !== null &&
      Date.parse(freshness.nextExpectedAt) < asOf
    ) {
      context.addIssue({
        code: "custom",
        message: "nextExpectedAt must not be in the past",
        path: ["nextExpectedAt"],
      });
    }
  });

export const PUBLIC_SYSTEM_STATUSES = [
  "operational",
  "degraded",
  "maintenance",
  "unavailable",
] as const;
export const publicSystemStatusValueSchema = z.enum(PUBLIC_SYSTEM_STATUSES);

export const publicSystemComponentSchema = z
  .object({
    id: publicIdSchema,
    name: z.string().trim().min(1).max(120),
    status: publicSystemStatusValueSchema,
    checkedAt: isoDateTimeSchema,
  })
  .strict();

export const publicSystemStatusSchema = z
  .object({
    status: publicSystemStatusValueSchema,
    checkedAt: isoDateTimeSchema,
    components: z.array(publicSystemComponentSchema).max(32),
  })
  .strict();

export type PublicActivityKind = z.infer<typeof publicActivityKindSchema>;
export type PublishedObservationStatus = z.infer<
  typeof publishedObservationStatusSchema
>;
export type PublicRecentActivityItem = z.infer<
  typeof publicRecentActivityItemSchema
>;
export type FreshnessStatus = z.infer<typeof freshnessStatusValueSchema>;
export type PublicFreshnessStatus = z.infer<typeof publicFreshnessStatusSchema>;
export type PublicSystemStatusValue = z.infer<
  typeof publicSystemStatusValueSchema
>;
export type PublicSystemComponent = z.infer<typeof publicSystemComponentSchema>;
export type PublicSystemStatus = z.infer<typeof publicSystemStatusSchema>;

export const publicAggregateSignalSchema = z
  .object({
    id: publicIdSchema,
    scope: z
      .object({
        kind: z.enum(["global", "set", "product", "region", "retailer", "batch"]),
        id: z.string().min(1).max(128),
        label: z.string().min(1).max(160),
      })
      .strict(),
    metric: z.enum(["hit_rate", "rarity_rate"]),
    estimate: probabilitySchema.nullable(),
    credibleInterval: publicCredibleIntervalSchema.nullable(),
    openingCount: z.number().int().min(1).max(10_000_000),
    packCount: z.number().int().min(1).max(100_000_000),
    independentSources: z.number().int().min(1).max(1_000_000),
    label: signalLabelSchema,
    evidenceTier: statisticalEvidenceTierSchema,
    asOf: z.string().datetime({ offset: true }),
    isFixture: z.boolean(),
  })
  .strict()
  .superRefine((signal, context) => {
    if (signal.openingCount > signal.packCount) {
      context.addIssue({
        code: "custom",
        message: "openingCount must not exceed packCount",
        path: ["openingCount"],
      });
    }
    if (signal.independentSources > signal.openingCount) {
      context.addIssue({
        code: "custom",
        message: "independentSources must not exceed openingCount",
        path: ["independentSources"],
      });
    }

    const insufficient = signal.packCount < 30 || signal.independentSources < 3;
    if (insufficient) {
      if (signal.label !== "Insufficient sample") {
        context.addIssue({
          code: "custom",
          message: "insufficient signals require the Insufficient sample label",
          path: ["label"],
        });
      }
      if (signal.estimate !== null || signal.credibleInterval !== null) {
        context.addIssue({
          code: "custom",
          message: "insufficient signals must withhold estimates and intervals",
          path: ["estimate"],
        });
      }
      return;
    }

    if (signal.label === "Insufficient sample") {
      context.addIssue({
        code: "custom",
        message: "sufficient signals cannot use the Insufficient sample label",
        path: ["label"],
      });
    }
    if (signal.estimate === null || signal.credibleInterval === null) {
      context.addIssue({
        code: "custom",
        message: "sufficient signals require an estimate and interval",
        path: ["estimate"],
      });
      return;
    }
    const { low, high } = signal.credibleInterval;
    if (low > high) {
      context.addIssue({
        code: "custom",
        message: "credibleInterval.low must not exceed credibleInterval.high",
        path: ["credibleInterval", "low"],
      });
    }
    if (signal.estimate < low || signal.estimate > high) {
      context.addIssue({
        code: "custom",
        message: "estimate must be inside the credible interval",
        path: ["estimate"],
      });
    }
    if (
      (signal.label === "Watch" || signal.label === "Possible anomaly") &&
      signal.packCount < 200
    ) {
      context.addIssue({
        code: "custom",
        message: "Watch and Possible anomaly require at least 200 packs",
        path: ["label"],
      });
    }
  });

export type PublicAggregateSignal = z.infer<
  typeof publicAggregateSignalSchema
>;

export const PUBLIC_PAYLOAD_SCHEMA_VERSION = "1.0.0" as const;

export const publicTrendPointSchema = z
  .object({
    date: isoDateSchema,
    observedRate: probabilitySchema.nullable(),
    baselineRate: probabilitySchema.nullable(),
    packsObserved: z.number().int().min(0).max(100_000_000),
    completeOpenings: z.number().int().min(0).max(10_000_000),
    independentSources: z.number().int().min(0).max(1_000_000),
  })
  .strict()
  .superRefine((point, context) => {
    if (point.completeOpenings > point.packsObserved) {
      context.addIssue({
        code: "custom",
        message: "completeOpenings must not exceed packsObserved",
        path: ["completeOpenings"],
      });
    }
    if (point.independentSources > point.completeOpenings) {
      context.addIssue({
        code: "custom",
        message: "independentSources must not exceed completeOpenings",
        path: ["independentSources"],
      });
    }
    const insufficient = point.packsObserved < 30 || point.independentSources < 3;
    if (insufficient && (point.observedRate !== null || point.baselineRate !== null)) {
      context.addIssue({
        code: "custom",
        message: "insufficient trend evidence must withhold both rates",
        path: ["observedRate"],
      });
    }
    if (!insufficient && (point.observedRate === null || point.baselineRate === null)) {
      context.addIssue({
        code: "custom",
        message: "sufficient trend evidence must publish both rates",
        path: ["observedRate"],
      });
    }
  });

export const publicProductBreakdownSchema = z
  .object({
    productType: productTypeSchema,
    packsObserved: z.number().int().min(0).max(100_000_000),
    openings: z.number().int().min(0).max(10_000_000),
    hitRate: probabilitySchema.nullable(),
  })
  .strict()
  .superRefine((product, context) => {
    if (product.openings > product.packsObserved) {
      context.addIssue({
        code: "custom",
        message: "openings must not exceed packsObserved",
        path: ["openings"],
      });
    }
  });

const publicDetailSectionsShape = {
  trend: z.array(publicTrendPointSchema).max(366),
  signals: z.array(publicAggregateSignalSchema).max(100),
  recentActivity: z.array(publicRecentActivityItemSchema).max(100),
} as const;

export const publicSetDetailSchema = z
  .object({
    summary: publicSetSummarySchema,
    products: z.array(publicProductBreakdownSchema).max(32),
    ...publicDetailSectionsShape,
  })
  .strict();

export const publicRegionDetailSchema = z
  .object({
    summary: publicRegionSummarySchema,
    sets: z.array(publicSetSummarySchema).max(100),
    ...publicDetailSectionsShape,
  })
  .strict();

export const publicRetailerDetailSchema = z
  .object({
    summary: publicRetailerSummarySchema,
    sets: z.array(publicSetSummarySchema).max(100),
    ...publicDetailSectionsShape,
  })
  .strict();

export const publicBatchDetailSchema = z
  .object({
    summary: publicBatchSummarySchema,
    products: z.array(publicProductBreakdownSchema).max(32),
    ...publicDetailSectionsShape,
  })
  .strict();

export const DATA_MODES = ["demo", "live", "unavailable"] as const;
export const dataModeSchema = z.enum(DATA_MODES);

export const publicDashboardSummarySchema = z
  .object({
    packsObserved: z.number().int().min(0).max(100_000_000),
    openings: z.number().int().min(0).max(10_000_000),
    verifiedSources: z.number().int().min(0).max(1_000_000),
    coverageDays: z.number().int().min(0).max(36_600),
    baselineHitRate: probabilitySchema.nullable(),
  })
  .strict()
  .superRefine((summary, context) => {
    if (summary.openings > summary.packsObserved) {
      context.addIssue({
        code: "custom",
        message: "openings must not exceed packsObserved",
        path: ["openings"],
      });
    }
    if (summary.verifiedSources > summary.openings) {
      context.addIssue({
        code: "custom",
        message: "verifiedSources must not exceed openings",
        path: ["verifiedSources"],
      });
    }
    if (
      (summary.packsObserved < 30 || summary.verifiedSources < 3) &&
      summary.baselineHitRate !== null
    ) {
      context.addIssue({
        code: "custom",
        message: "insufficient dashboard evidence must withhold the baseline rate",
        path: ["baselineHitRate"],
      });
    }
  });

export const publicDashboardOverviewSchema = z
  .object({
    schemaVersion: z.literal(PUBLIC_PAYLOAD_SCHEMA_VERSION),
    mode: dataModeSchema,
    generatedAt: isoDateTimeSchema,
    summary: publicDashboardSummarySchema,
    freshness: publicFreshnessStatusSchema,
    system: publicSystemStatusSchema,
  })
  .strict();

export type PublicTrendPoint = z.infer<typeof publicTrendPointSchema>;
export type PublicProductBreakdown = z.infer<
  typeof publicProductBreakdownSchema
>;
export type PublicSetDetail = z.infer<typeof publicSetDetailSchema>;
export type PublicRegionDetail = z.infer<typeof publicRegionDetailSchema>;
export type PublicRetailerDetail = z.infer<typeof publicRetailerDetailSchema>;
export type PublicBatchDetail = z.infer<typeof publicBatchDetailSchema>;
export type DataMode = z.infer<typeof dataModeSchema>;
export type PublicDashboardSummary = z.infer<
  typeof publicDashboardSummarySchema
>;
export type PublicDashboardOverview = z.infer<
  typeof publicDashboardOverviewSchema
>;

export const cursorPaginationSchema = z
  .object({
    limit: z.number().int().min(1).max(100),
    nextCursor: z.string().trim().min(1).max(512).regex(/^\S+$/).nullable(),
    hasMore: z.boolean(),
  })
  .strict()
  .superRefine((pagination, context) => {
    if (pagination.hasMore !== (pagination.nextCursor !== null)) {
      context.addIssue({
        code: "custom",
        message: "hasMore and nextCursor must agree",
        path: ["hasMore"],
      });
    }
  });

export const offsetPaginationSchema = z
  .object({
    page: z.number().int().min(1).max(10_000_000),
    pageSize: z.number().int().min(1).max(100),
    totalItems: z.number().int().min(0).max(100_000_000),
    totalPages: z.number().int().min(0).max(10_000_000),
    hasNextPage: z.boolean(),
    hasPreviousPage: z.boolean(),
  })
  .strict()
  .superRefine((pagination, context) => {
    const expectedPages = Math.ceil(pagination.totalItems / pagination.pageSize);
    if (pagination.totalPages !== expectedPages) {
      context.addIssue({
        code: "custom",
        message: "totalPages must match totalItems and pageSize",
        path: ["totalPages"],
      });
    }
    const expectedPrevious = pagination.totalPages > 0 && pagination.page > 1;
    const expectedNext = pagination.page < pagination.totalPages;
    if (pagination.hasPreviousPage !== expectedPrevious) {
      context.addIssue({
        code: "custom",
        message: "hasPreviousPage is inconsistent with page",
        path: ["hasPreviousPage"],
      });
    }
    if (pagination.hasNextPage !== expectedNext) {
      context.addIssue({
        code: "custom",
        message: "hasNextPage is inconsistent with totalPages",
        path: ["hasNextPage"],
      });
    }
    if (pagination.totalPages > 0 && pagination.page > pagination.totalPages) {
      context.addIssue({
        code: "custom",
        message: "page must not exceed totalPages",
        path: ["page"],
      });
    }
    if (pagination.totalPages === 0 && pagination.page !== 1) {
      context.addIssue({
        code: "custom",
        message: "an empty result uses page 1",
        path: ["page"],
      });
    }
  });

export const createCursorPageSchema = <T extends z.ZodType>(
  itemSchema: T,
  maxItems = 100,
) =>
  z
    .object({
      items: z.array(itemSchema).max(maxItems),
      pagination: cursorPaginationSchema,
    })
    .strict()
    .superRefine((page, context) => {
      if (page.items.length > page.pagination.limit) {
        context.addIssue({
          code: "custom",
          message: "items must not exceed the requested limit",
          path: ["items"],
        });
      }
    });

export const publicSetPageSchema = createCursorPageSchema(publicSetSummarySchema);
export const publicRegionPageSchema = createCursorPageSchema(publicRegionSummarySchema);
export const publicRetailerPageSchema = createCursorPageSchema(
  publicRetailerSummarySchema,
);
export const publicBatchPageSchema = createCursorPageSchema(publicBatchSummarySchema);
export const publicRecentActivityPageSchema = createCursorPageSchema(
  publicRecentActivityItemSchema,
);
export const publicSignalPageSchema = createCursorPageSchema(
  publicAggregateSignalSchema,
);

export const publicCompactDashboardPayloadSchema = z
  .object({
    overview: publicDashboardOverviewSchema,
    sets: z.array(publicSetSummarySchema).max(50),
    regions: z.array(publicRegionSummarySchema).max(50),
    retailers: z.array(publicRetailerSummarySchema).max(50),
    batches: z.array(publicBatchSummarySchema).max(50),
    recentActivity: z.array(publicRecentActivityItemSchema).max(50),
    signals: z.array(publicAggregateSignalSchema).max(50),
  })
  .strict();

export const paginationSchema = cursorPaginationSchema;
export const publicCompactPayloadSchema = publicCompactDashboardPayloadSchema;

export type CursorPagination = z.infer<typeof cursorPaginationSchema>;
export type OffsetPagination = z.infer<typeof offsetPaginationSchema>;
export type PublicSetPage = z.infer<typeof publicSetPageSchema>;
export type PublicRegionPage = z.infer<typeof publicRegionPageSchema>;
export type PublicRetailerPage = z.infer<typeof publicRetailerPageSchema>;
export type PublicBatchPage = z.infer<typeof publicBatchPageSchema>;
export type PublicRecentActivityPage = z.infer<
  typeof publicRecentActivityPageSchema
>;
export type PublicSignalPage = z.infer<typeof publicSignalPageSchema>;
export type PublicCompactDashboardPayload = z.infer<
  typeof publicCompactDashboardPayloadSchema
>;

export const publicDashboardPayloadSchema = z
  .object({
    schemaVersion: z.literal(PUBLIC_PAYLOAD_SCHEMA_VERSION),
    generatedAt: z.string().datetime({ offset: true }),
    observations: z.array(publicOpeningObservationSchema).max(10_000),
    signals: z.array(publicAggregateSignalSchema).max(10_000),
  })
  .strict();

export type PublicDashboardPayload = z.infer<
  typeof publicDashboardPayloadSchema
>;

// Concise aliases keep consumer imports stable while preserving one schema instance.
export const EVIDENCE_STATUSES = PUBLIC_OBSERVATION_STATUSES;
export const evidenceStatusSchema = publicObservationStatusSchema;
export const dashboardOverviewSchema = publicDashboardOverviewSchema;
export const setSummarySchema = publicSetSummarySchema;
export const setDetailSchema = publicSetDetailSchema;
export const regionSummarySchema = publicRegionSummarySchema;
export const regionDetailSchema = publicRegionDetailSchema;
export const retailerSummarySchema = publicRetailerSummarySchema;
export const retailerDetailSchema = publicRetailerDetailSchema;
export const batchSummarySchema = publicBatchSummarySchema;
export const batchDetailSchema = publicBatchDetailSchema;
export const recentActivitySchema = publicRecentActivityItemSchema;
export const publicSignalSchema = publicAggregateSignalSchema;
export const freshnessSchema = publicFreshnessStatusSchema;
export const systemStatusSchema = publicSystemStatusSchema;
export const compactDashboardPayloadSchema =
  publicCompactDashboardPayloadSchema;

export type EvidenceStatus = PublicObservationStatus;
export type DashboardOverview = PublicDashboardOverview;
export type SetSummary = PublicSetSummary;
export type SetDetail = PublicSetDetail;
export type RegionSummary = PublicRegionSummary;
export type RegionDetail = PublicRegionDetail;
export type RetailerSummary = PublicRetailerSummary;
export type RetailerDetail = PublicRetailerDetail;
export type BatchSummary = PublicBatchSummary;
export type BatchDetail = PublicBatchDetail;
export type RecentActivity = PublicRecentActivityItem;
export type PublicSignal = PublicAggregateSignal;
export type SystemStatus = PublicSystemStatus;
export type CompactDashboardPayload = PublicCompactDashboardPayload;
export type Pagination = CursorPagination;
