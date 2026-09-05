import { describe, expect, it } from "vitest";

import { defaultWorldHeatMetric, normalizeWorldHeatMetric } from "./world-map-query";

describe("world map query", () => {
  it("accepts only one exact supported metric", () => {
    expect(normalizeWorldHeatMetric("coverage")).toBe("coverage");
    expect(normalizeWorldHeatMetric("delta")).toBe("delta");
    expect(normalizeWorldHeatMetric("rate")).toBe("rate");
    expect(normalizeWorldHeatMetric("hits")).toBeUndefined();
    expect(normalizeWorldHeatMetric(["coverage", "rate"])).toBeUndefined();
    expect(normalizeWorldHeatMetric(undefined)).toBeUndefined();
  });

  it("defaults to visible coverage until an exact country sample rate is published", () => {
    expect(defaultWorldHeatMetric(0)).toBe("coverage");
    expect(defaultWorldHeatMetric(1)).toBe("rate");
  });
});
