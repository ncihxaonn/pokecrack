import { describe, expect, it } from "vitest";

import {
  BAYES_DEFAULTS,
  COLLECTOR_TYPES,
  DATA_STATES,
  DEFAULT_DATA_STATE,
  EVIDENCE_TIERS,
  FREE_TIER_LIMIT_DEFAULTS,
  MVP_SCOPE,
  MVP_PRODUCT_TYPES,
  PUBLIC_SIGNAL_LABELS,
  SCHEDULE_DEFAULTS,
  SHARED_CONFIG_DEFAULTS,
  bayesConfigSchema,
  collectorTypeSchema,
  dataStateSchema,
  evidenceTierSchema,
  freeTierLimitConfigSchema,
  mvpProductTypeSchema,
  mvpScopeSchema,
  publicSignalLabelSchema,
  safeSharedConfigSchema,
  scheduleConfigSchema,
  sharedConfigSchema,
} from "../src/index.js";

describe("shared collector vocabulary", () => {
  it("accepts only the six canonical collector types", () => {
    expect(COLLECTOR_TYPES).toEqual([
      "official_api",
      "scrapling_http",
      "scrapling_dynamic",
      "opencli_authenticated",
      "manual_import",
      "disabled",
    ]);

    for (const collector of COLLECTOR_TYPES) {
      expect(collectorTypeSchema.safeParse(collector).success).toBe(true);
    }
    expect(collectorTypeSchema.safeParse("youtube").success).toBe(false);
    expect(collectorTypeSchema.safeParse("opencli").success).toBe(false);
  });
});


describe("shared evidence vocabulary", () => {
  it("accepts only evidence tiers A through D", () => {
    expect(EVIDENCE_TIERS).toEqual(["A", "B", "C", "D"]);

    for (const tier of EVIDENCE_TIERS) {
      expect(evidenceTierSchema.safeParse(tier).success).toBe(true);
    }
    expect(evidenceTierSchema.safeParse("E").success).toBe(false);
    expect(evidenceTierSchema.safeParse("activity-only").success).toBe(false);
  });
});


describe("shared data-state vocabulary", () => {
  it("distinguishes demo, live, and unavailable public data", () => {
    expect(DATA_STATES).toEqual(["demo", "live", "unavailable"]);

    for (const state of DATA_STATES) {
      expect(dataStateSchema.safeParse(state).success).toBe(true);
    }
    expect(dataStateSchema.safeParse("fixture").success).toBe(false);
    expect(dataStateSchema.safeParse("loading").success).toBe(false);
  });
});


describe("public signal-label vocabulary", () => {
  it("accepts only the four non-predictive public labels", () => {
    expect(PUBLIC_SIGNAL_LABELS).toEqual([
      "Insufficient sample",
      "No significant signal",
      "Watch",
      "Possible anomaly",
    ]);

    for (const label of PUBLIC_SIGNAL_LABELS) {
      expect(publicSignalLabelSchema.safeParse(label).success).toBe(true);
    }
    expect(publicSignalLabelSchema.safeParse("Hot").success).toBe(false);
    expect(publicSignalLabelSchema.safeParse("Guaranteed hit").success).toBe(false);
  });
});


describe("MVP observation scope", () => {
  it("allows only Australian English observations of the three supported products", () => {
    expect(MVP_SCOPE).toEqual({
      country: "Australia",
      countryCode: "AU",
      language: "English",
      languageCode: "en",
      productTypes: ["booster_box", "etb", "booster_bundle"],
    });
    expect(MVP_PRODUCT_TYPES).toEqual([
      "booster_box",
      "etb",
      "booster_bundle",
    ]);
    expect(mvpScopeSchema.safeParse(MVP_SCOPE).success).toBe(true);

    expect(mvpProductTypeSchema.safeParse("other").success).toBe(false);
    expect(mvpProductTypeSchema.safeParse("elite_trainer_box").success).toBe(false);
    expect(
      mvpScopeSchema.safeParse({ ...MVP_SCOPE, countryCode: "US" }).success,
    ).toBe(false);
    expect(
      mvpScopeSchema.safeParse({ ...MVP_SCOPE, languageCode: "ja" }).success,
    ).toBe(false);
  });
});


describe("scheduler defaults", () => {
  it("uses the documented bounded five-field cron schedule", () => {
    expect(SCHEDULE_DEFAULTS).toEqual({
      officialApi: "0 */6 * * *",
      publicCollection: "15 */6 * * *",
      authCollection: "30 */12 * * *",
      catalogSync: "0 2 * * *",
      aggregates: "5 * * * *",
      cleanup: "30 3 * * *",
      backup: "0 4 * * *",
      browserCheck: "*/30 * * * *",
    });
    expect(scheduleConfigSchema.safeParse(SCHEDULE_DEFAULTS).success).toBe(true);
    expect(
      scheduleConfigSchema.safeParse({ ...SCHEDULE_DEFAULTS, apiKey: "not-safe" })
        .success,
    ).toBe(false);
    expect(
      scheduleConfigSchema.safeParse({
        ...SCHEDULE_DEFAULTS,
        officialApi: "@hourly",
      }).success,
    ).toBe(false);
  });
});


describe("free-tier operating limits", () => {
  it("uses the documented warning and critical thresholds", () => {
    expect(FREE_TIER_LIMIT_DEFAULTS).toEqual({
      databaseWarningMb: 350,
      databaseCriticalMb: 425,
      storageWarningMb: 700,
      storageCriticalMb: 850,
      monthlyEgressWarningGb: 3.5,
    });
    expect(
      freeTierLimitConfigSchema.safeParse(FREE_TIER_LIMIT_DEFAULTS).success,
    ).toBe(true);
    expect(
      freeTierLimitConfigSchema.safeParse({
        ...FREE_TIER_LIMIT_DEFAULTS,
        databaseWarningMb: 426,
      }).success,
    ).toBe(false);
    expect(
      freeTierLimitConfigSchema.safeParse({
        ...FREE_TIER_LIMIT_DEFAULTS,
        storageWarningMb: -1,
      }).success,
    ).toBe(false);
    expect(
      freeTierLimitConfigSchema.safeParse({
        ...FREE_TIER_LIMIT_DEFAULTS,
        serviceRoleKey: "forbidden",
      }).success,
    ).toBe(false);
  });
});


describe("empirical-Bayes and signal defaults", () => {
  it("uses the documented publication and probability thresholds", () => {
    expect(BAYES_DEFAULTS).toEqual({
      priorStrength: 50,
      credibleIntervalLevel: 0.9,
      minRateDisplayPacks: 30,
      minSignalPacks: 200,
      minSignalSources: 3,
      minPracticalUplift: 0.2,
      minWatchProbability: 0.9,
      minAnomalyProbability: 0.95,
    });
    expect(bayesConfigSchema.safeParse(BAYES_DEFAULTS).success).toBe(true);
    expect(
      bayesConfigSchema.safeParse({
        ...BAYES_DEFAULTS,
        minRateDisplayPacks: 201,
      }).success,
    ).toBe(false);
    expect(
      bayesConfigSchema.safeParse({
        ...BAYES_DEFAULTS,
        minWatchProbability: 0.96,
      }).success,
    ).toBe(false);
    expect(
      bayesConfigSchema.safeParse({
        ...BAYES_DEFAULTS,
        priorStrength: 0,
      }).success,
    ).toBe(false);
  });
});


describe("safe shared configuration", () => {
  it("publishes only strict non-secret defaults", () => {
    expect(DEFAULT_DATA_STATE).toBe("demo");
    expect(SHARED_CONFIG_DEFAULTS).toEqual({
      dataState: "demo",
      scope: MVP_SCOPE,
      schedules: SCHEDULE_DEFAULTS,
      freeTierLimits: FREE_TIER_LIMIT_DEFAULTS,
      bayes: BAYES_DEFAULTS,
    });
    expect(
      sharedConfigSchema.safeParse(SHARED_CONFIG_DEFAULTS).success,
    ).toBe(true);
    expect(safeSharedConfigSchema).toBe(sharedConfigSchema);
    expect(JSON.stringify(SHARED_CONFIG_DEFAULTS)).not.toMatch(
      /api.?key|password|secret|token|credential|service.?role/i,
    );
    expect(
      sharedConfigSchema.safeParse({
        ...SHARED_CONFIG_DEFAULTS,
        serviceRoleKey: "forbidden",
      }).success,
    ).toBe(false);
  });
});
