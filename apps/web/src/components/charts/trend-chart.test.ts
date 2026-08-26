import { describe, expect, it } from "vitest";

import { getTrendAnimationOptions } from "./trend-chart";

describe("trend chart motion", () => {
  it("turns ECharts animation off for reduced-motion users", () => {
    expect(getTrendAnimationOptions(true)).toEqual({
      animation: false,
      animationDuration: 0,
    });
    expect(getTrendAnimationOptions(false)).toEqual({
      animation: true,
      animationDuration: 450,
    });
  });
});
