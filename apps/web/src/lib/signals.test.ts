import { describe, expect, it } from "vitest";

import {
  PUBLIC_SIGNAL_LABELS,
  getConfidence,
  getSignalPresentation,
} from "./signals";

describe("signal presentation", () => {
  it.each([
    ["ready", "No significant signal", "neutral"],
    ["watch", "Watch", "warning"],
    ["anomaly", "Possible anomaly", "alert"],
    ["insufficient", "Insufficient sample", "muted"],
  ] as const)("maps %s to a restrained public label", (state, label, tone) => {
    expect(getSignalPresentation(state)).toMatchObject({ label, tone });
  });

  it("exports only the four approved public signal labels", () => {
    expect(PUBLIC_SIGNAL_LABELS).toEqual([
      "Insufficient sample",
      "No significant signal",
      "Watch",
      "Possible anomaly",
    ]);
  });

  it("never uses predictive or promotional signal labels", () => {
    const copy = ["ready", "watch", "anomaly", "insufficient"]
      .map((state) => getSignalPresentation(state as Parameters<typeof getSignalPresentation>[0]).label)
      .join(" ")
      .toLowerCase();

    expect(copy).not.toMatch(/guaranteed|lucky|best|hot/);
  });
});

describe("confidence presentation", () => {
  it("withholds confidence when a rate is unavailable", () => {
    expect(
      getConfidence({
        packsObserved: 500,
        credibleInterval: null,
        state: "insufficient",
      }),
    ).toEqual({ label: "Unavailable", detail: "No outcome interval is published." });
  });

  it("uses sample size and interval width rather than the direction of a result", () => {
    expect(
      getConfidence({
        packsObserved: 1_200,
        credibleInterval: { low: 0.12, high: 0.16 },
        state: "ready",
      }).label,
    ).toBe("High");
    expect(
      getConfidence({
        packsObserved: 350,
        credibleInterval: { low: 0.1, high: 0.17 },
        state: "watch",
      }).label,
    ).toBe("Moderate");
    expect(
      getConfidence({
        packsObserved: 74,
        credibleInterval: { low: 0.04, high: 0.24 },
        state: "insufficient",
      }).label,
    ).toBe("Limited");
  });
});
