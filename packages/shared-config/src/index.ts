import { z } from "zod";

export const COLLECTOR_TYPES = [
  "official_api",
  "scrapling_http",
  "scrapling_dynamic",
  "opencli_authenticated",
  "manual_import",
  "disabled",
] as const;

export const collectorTypeSchema = z.enum(COLLECTOR_TYPES);

export type CollectorType = z.infer<typeof collectorTypeSchema>;

export const EVIDENCE_TIERS = ["A", "B", "C", "D"] as const;

export const evidenceTierSchema = z.enum(EVIDENCE_TIERS);

export type EvidenceTier = z.infer<typeof evidenceTierSchema>;

export const DATA_STATES = ["demo", "live", "unavailable"] as const;

export const dataStateSchema = z.enum(DATA_STATES);

export type DataState = z.infer<typeof dataStateSchema>;

export const PUBLIC_SIGNAL_LABELS = [
  "Insufficient sample",
  "No significant signal",
  "Watch",
  "Possible anomaly",
] as const;

export const publicSignalLabelSchema = z.enum(PUBLIC_SIGNAL_LABELS);

export type PublicSignalLabel = z.infer<typeof publicSignalLabelSchema>;

export const MVP_PRODUCT_TYPES = [
  "booster_box",
  "etb",
  "booster_bundle",
] as const;

export const mvpProductTypeSchema = z.enum(MVP_PRODUCT_TYPES);

export const MVP_SCOPE = {
  country: "Australia",
  countryCode: "AU",
  language: "English",
  languageCode: "en",
  productTypes: MVP_PRODUCT_TYPES,
} as const;

export const mvpScopeSchema = z
  .object({
    country: z.literal("Australia"),
    countryCode: z.literal("AU"),
    language: z.literal("English"),
    languageCode: z.literal("en"),
    productTypes: z.tuple([
      z.literal("booster_box"),
      z.literal("etb"),
      z.literal("booster_bundle"),
    ]),
  })
  .strict();

export type MvpProductType = z.infer<typeof mvpProductTypeSchema>;
export type MvpScope = z.infer<typeof mvpScopeSchema>;

export const cronExpressionSchema = z
  .string()
  .max(100)
  .regex(/^(?:[0-9*/,-]+ ){4}[0-9*/,-]+$/);

export const scheduleConfigSchema = z
  .object({
    officialApi: cronExpressionSchema,
    publicCollection: cronExpressionSchema,
    authCollection: cronExpressionSchema,
    catalogSync: cronExpressionSchema,
    aggregates: cronExpressionSchema,
    cleanup: cronExpressionSchema,
    backup: cronExpressionSchema,
    browserCheck: cronExpressionSchema,
  })
  .strict();

export const SCHEDULE_DEFAULTS = {
  officialApi: "0 */6 * * *",
  publicCollection: "15 */6 * * *",
  authCollection: "30 */12 * * *",
  catalogSync: "0 2 * * *",
  aggregates: "5 * * * *",
  cleanup: "30 3 * * *",
  backup: "0 4 * * *",
  browserCheck: "*/30 * * * *",
} as const satisfies z.input<typeof scheduleConfigSchema>;

export type ScheduleConfig = z.infer<typeof scheduleConfigSchema>;

const nonNegativeMegabytesSchema = z.number().int().finite().min(0).max(1_000_000);

export const freeTierLimitConfigSchema = z
  .object({
    databaseWarningMb: nonNegativeMegabytesSchema,
    databaseCriticalMb: nonNegativeMegabytesSchema,
    storageWarningMb: nonNegativeMegabytesSchema,
    storageCriticalMb: nonNegativeMegabytesSchema,
    monthlyEgressWarningGb: z.number().finite().min(0).max(1_000_000),
  })
  .strict()
  .superRefine((limits, context) => {
    if (limits.databaseWarningMb > limits.databaseCriticalMb) {
      context.addIssue({
        code: "custom",
        message: "database warning must not exceed the critical threshold",
        path: ["databaseWarningMb"],
      });
    }
    if (limits.storageWarningMb > limits.storageCriticalMb) {
      context.addIssue({
        code: "custom",
        message: "storage warning must not exceed the critical threshold",
        path: ["storageWarningMb"],
      });
    }
  });

export const FREE_TIER_LIMIT_DEFAULTS = {
  databaseWarningMb: 350,
  databaseCriticalMb: 425,
  storageWarningMb: 700,
  storageCriticalMb: 850,
  monthlyEgressWarningGb: 3.5,
} as const satisfies z.input<typeof freeTierLimitConfigSchema>;

export type FreeTierLimitConfig = z.infer<typeof freeTierLimitConfigSchema>;

const probabilitySchema = z.number().finite().min(0).max(1);
const positiveIntegerSchema = z.number().int().min(1).max(100_000_000);

export const bayesConfigSchema = z
  .object({
    priorStrength: z.number().finite().positive().max(1_000_000),
    credibleIntervalLevel: z.literal(0.9),
    minRateDisplayPacks: positiveIntegerSchema,
    minSignalPacks: positiveIntegerSchema,
    minSignalSources: positiveIntegerSchema,
    minPracticalUplift: z.number().finite().min(0).max(10),
    minWatchProbability: probabilitySchema,
    minAnomalyProbability: probabilitySchema,
  })
  .strict()
  .superRefine((config, context) => {
    if (config.minRateDisplayPacks > config.minSignalPacks) {
      context.addIssue({
        code: "custom",
        message: "rate display threshold must not exceed signal threshold",
        path: ["minRateDisplayPacks"],
      });
    }
    if (config.minWatchProbability > config.minAnomalyProbability) {
      context.addIssue({
        code: "custom",
        message: "watch probability must not exceed anomaly probability",
        path: ["minWatchProbability"],
      });
    }
  });

export const BAYES_DEFAULTS = {
  priorStrength: 50,
  credibleIntervalLevel: 0.9,
  minRateDisplayPacks: 30,
  minSignalPacks: 200,
  minSignalSources: 3,
  minPracticalUplift: 0.2,
  minWatchProbability: 0.9,
  minAnomalyProbability: 0.95,
} as const satisfies z.input<typeof bayesConfigSchema>;

export type BayesConfig = z.infer<typeof bayesConfigSchema>;

export const DEFAULT_DATA_STATE = "demo" satisfies DataState;

export const sharedConfigSchema = z
  .object({
    dataState: dataStateSchema,
    scope: mvpScopeSchema,
    schedules: scheduleConfigSchema,
    freeTierLimits: freeTierLimitConfigSchema,
    bayes: bayesConfigSchema,
  })
  .strict();

export const safeSharedConfigSchema = sharedConfigSchema;

export const SHARED_CONFIG_DEFAULTS = {
  dataState: DEFAULT_DATA_STATE,
  scope: MVP_SCOPE,
  schedules: SCHEDULE_DEFAULTS,
  freeTierLimits: FREE_TIER_LIMIT_DEFAULTS,
  bayes: BAYES_DEFAULTS,
} as const;

export type SharedConfig = z.infer<typeof sharedConfigSchema>;
