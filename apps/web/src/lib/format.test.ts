import { describe, expect, it } from "vitest";

import {
  formatCompactNumber,
  formatDate,
  formatDateTime,
  formatProbability,
  formatSignedProbability,
} from "./format";

describe("format helpers", () => {
  it("formats probabilities without implying precision beyond one decimal place", () => {
    expect(formatProbability(0.142)).toBe("14.2%");
    expect(formatProbability(null)).toBe("Withheld");
    expect(formatSignedProbability(0.032)).toBe("+3.2 pp");
    expect(formatSignedProbability(-0.01)).toBe("−1.0 pp");
    expect(formatSignedProbability(null)).toBe("—");
  });

  it("formats counts compactly while preserving small exact values", () => {
    expect(formatCompactNumber(987)).toBe("987");
    expect(formatCompactNumber(4_872)).toBe("4.9K");
    expect(formatCompactNumber(1_250_000)).toBe("1.3M");
  });

  it("formats dates in UTC and rejects invalid timestamps safely", () => {
    expect(formatDate("2026-08-25")).toBe("25 Aug 2026");
    expect(formatDateTime("2026-08-25T03:00:00.000Z")).toBe(
      "25 Aug 2026, 03:00 UTC",
    );
    expect(formatDateTime(null)).toBe("Never");
    expect(formatDate("not-a-date")).toBe("Unavailable");
  });
});
