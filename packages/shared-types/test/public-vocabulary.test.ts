import { describe, expect, it } from "vitest";

import {
  COLLECTOR_ROUTES,
  EVIDENCE_TIERS,
  PRODUCT_TYPES,
  PUBLIC_OBSERVATION_STATUSES,
  SIGNAL_LABELS,
  collectorRouteSchema,
  productTypeSchema,
} from "../src/index.js";

describe("public vocabulary", () => {
  it("uses the exact evidence decision statuses", () => {
    expect(PUBLIC_OBSERVATION_STATUSES).toEqual([
      "accepted",
      "activity_only",
      "rejected",
    ]);
  });

  it("uses the exact evidence tiers", () => {
    expect(EVIDENCE_TIERS).toEqual(["A", "B", "C", "D"]);
  });

  it("uses the exact non-predictive signal labels", () => {
    expect(SIGNAL_LABELS).toEqual([
      "Insufficient sample",
      "No significant signal",
      "Watch",
      "Possible anomaly",
    ]);
    expect(SIGNAL_LABELS.join(" " )).not.toMatch(/hot|lucky|guarantee|best/i);
  });

  it("uses the exact product taxonomy and rejects display aliases", () => {
    expect(PRODUCT_TYPES).toEqual([
      "booster_box",
      "etb",
      "booster_bundle",
      "other",
      "unknown",
    ]);
    expect(productTypeSchema.safeParse("etb").success).toBe(true);
    expect(productTypeSchema.safeParse("elite_trainer_box").success).toBe(false);
  });

  it("uses the collector routes shared with the worker", () => {
    expect(COLLECTOR_ROUTES).toEqual([
      "official_api",
      "scrapling_http",
      "scrapling_dynamic",
      "opencli_authenticated",
      "manual_import",
      "disabled",
    ]);
    expect(collectorRouteSchema.safeParse("youtube").success).toBe(false);
  });
});
