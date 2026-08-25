import { describe, expect, it } from "vitest";

import { publicAggregateSignalSchema } from "../src/index.js";

const validSignal = {
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

describe("publicAggregateSignalSchema", () => {
  it("requires a coherent bounded interval and strict public shape", () => {
    expect(publicAggregateSignalSchema.parse(validSignal)).toEqual(validSignal);

    expect(() =>
      publicAggregateSignalSchema.parse({
        ...validSignal,
        credibleInterval: { low: 0.3, high: 0.2, level: 0.9 },
      }),
    ).toThrow();

    expect(() =>
      publicAggregateSignalSchema.parse({
        ...validSignal,
        estimate: 0.5,
        credibleInterval: { low: 0.1, high: 0.4, level: 0.9 },
      }),
    ).toThrow();

  });

  it("publishes rates only from statistical evidence and coherent sample counts", () => {
    expect(
      publicAggregateSignalSchema.safeParse({
        ...validSignal,
        evidenceTier: "C",
      }).success,
    ).toBe(false);
    expect(
      publicAggregateSignalSchema.safeParse({
        ...validSignal,
        openingCount: validSignal.packCount + 1,
      }).success,
    ).toBe(false);
  });

  it("withholds inference until pack and source minimums are met", () => {
    const insufficient = {
      ...validSignal,
      openingCount: 1,
      packCount: 1,
      independentSources: 1,
      estimate: null,
      credibleInterval: null,
      label: "Insufficient sample" as const,
    };

    expect(publicAggregateSignalSchema.safeParse(insufficient).success).toBe(true);
    expect(
      publicAggregateSignalSchema.safeParse({
        ...insufficient,
        estimate: 0.5,
        credibleInterval: { low: 0.4, high: 0.6, level: 0.9 },
      }).success,
    ).toBe(false);
  });

  it("enforces the published 90 percent interval level", () => {
    expect(
      publicAggregateSignalSchema.safeParse({
        ...validSignal,
        credibleInterval: { low: 0.15, high: 0.38, level: 0.95 },
      }).success,
    ).toBe(false);
  });

  it("supports every public aggregate scope without accepting arbitrary scopes", () => {
    expect(
      publicAggregateSignalSchema.safeParse({
        ...validSignal,
        scope: { kind: "batch", id: "batch-1", label: "Batch 1" },
      }).success,
    ).toBe(true);
    expect(
      publicAggregateSignalSchema.safeParse({
        ...validSignal,
        scope: { kind: "author", id: "person-1", label: "Person" },
      }).success,
    ).toBe(false);
  });

  it.each(["rawAiOutput", "sourceUrl", "author", "jobPayload", "disclaimer"])(
    "rejects private signal field %s",
    (field) => {
      expect(
        publicAggregateSignalSchema.safeParse({ ...validSignal, [field]: "private" }).success,
      ).toBe(false);
    },
  );

  it("rejects private nested scope fields", () => {
    expect(
      publicAggregateSignalSchema.safeParse({
        ...validSignal,
        scope: { ...validSignal.scope, sourceUrl: "https://private.invalid" },
      }).success,
    ).toBe(false);
  });
});
