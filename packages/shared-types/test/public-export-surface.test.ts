import { describe, expect, it } from "vitest";

import {
  batchDetailSchema,
  batchSummarySchema,
  compactDashboardPayloadSchema,
  dashboardOverviewSchema,
  evidenceStatusSchema,
  publicBatchDetailSchema,
  publicBatchSummarySchema,
  publicCompactDashboardPayloadSchema,
  publicDashboardOverviewSchema,
  publicFreshnessStatusSchema,
  publicRecentActivityItemSchema,
  publicRegionDetailSchema,
  publicRegionSummarySchema,
  publicRetailerDetailSchema,
  publicRetailerSummarySchema,
  publicSetDetailSchema,
  publicSetSummarySchema,
  publicSignalSchema,
  publicAggregateSignalSchema,
  publicSystemStatusSchema,
  freshnessSchema,
  recentActivitySchema,
  regionDetailSchema,
  regionSummarySchema,
  retailerDetailSchema,
  retailerSummarySchema,
  setDetailSchema,
  setSummarySchema,
  systemStatusSchema,
} from "../src/index.js";

describe("stable public export surface", () => {
  it("provides concise aliases without duplicating schema behavior", () => {
    expect(evidenceStatusSchema).toBeDefined();
    expect(dashboardOverviewSchema).toBe(publicDashboardOverviewSchema);
    expect(setSummarySchema).toBe(publicSetSummarySchema);
    expect(setDetailSchema).toBe(publicSetDetailSchema);
    expect(regionSummarySchema).toBe(publicRegionSummarySchema);
    expect(regionDetailSchema).toBe(publicRegionDetailSchema);
    expect(retailerSummarySchema).toBe(publicRetailerSummarySchema);
    expect(retailerDetailSchema).toBe(publicRetailerDetailSchema);
    expect(batchSummarySchema).toBe(publicBatchSummarySchema);
    expect(batchDetailSchema).toBe(publicBatchDetailSchema);
    expect(recentActivitySchema).toBe(publicRecentActivityItemSchema);
    expect(publicSignalSchema).toBe(publicAggregateSignalSchema);
    expect(freshnessSchema).toBe(publicFreshnessStatusSchema);
    expect(systemStatusSchema).toBe(publicSystemStatusSchema);
    expect(compactDashboardPayloadSchema).toBe(publicCompactDashboardPayloadSchema);
  });
});
