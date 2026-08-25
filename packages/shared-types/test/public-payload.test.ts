import { describe, expect, it } from "vitest";

import { publicDashboardPayloadSchema } from "../src/index.js";

const observation = {
  id: "obs_demo_001",
  setCode: "DEMO-A",
  productName: "Demo Booster Box",
  productType: "booster_box",
  openedAt: "2026-01-15T12:00:00Z",
  packCount: 12,
  hitCount: 3,
  rarityCounts: { double_rare: 3 },
  evidenceTier: "A",
  status: "accepted",
  sourceKind: "fixture",
  isFixture: true,
} as const;

const signal = {
  id: "signal_demo_a",
  scope: { kind: "set", id: "DEMO-A", label: "Demo Set A" },
  metric: "hit_rate",
  estimate: 0.25,
  credibleInterval: { low: 0.15, high: 0.38, level: 0.9 },
  openingCount: 8,
  packCount: 200,
  independentSources: 3,
  label: "Watch",
  evidenceTier: "A",
  asOf: "2026-01-16T00:00:00Z",
  isFixture: true,
} as const;

describe("publicDashboardPayloadSchema", () => {
  it("validates the versioned public envelope strictly", () => {
    const payload = {
      schemaVersion: "1.0.0",
      generatedAt: "2026-01-16T00:00:00Z",
      observations: [observation],
      signals: [signal],
        } as const;

    expect(publicDashboardPayloadSchema.parse(payload)).toEqual(payload);
    expect(() =>
      publicDashboardPayloadSchema.parse({ ...payload, internalNotes: [] }),
    ).toThrow();
    expect(() =>
      publicDashboardPayloadSchema.parse({ ...payload, schemaVersion: "2" }),
    ).toThrow();
    expect(() =>
      publicDashboardPayloadSchema.parse({
        ...payload,
        disclaimer: "private",
      }),
    ).toThrow();
  });
});
