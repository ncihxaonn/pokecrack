import { describe, expect, it } from "vitest";
import { DEMO_PUBLIC_DATA } from "@/data/demo";
import { coverageDistribution, logPosition, overviewRows, rankCoverage, volumeSplit, type CoverageRow } from "./overview-charts";

const rows: CoverageRow[] = [
  { code: "AU", name: "Australia", packs: 1200, openings: 2, attribution: "Opening location" },
  { code: "JP", name: "Japan", packs: 29, openings: 10, attribution: "Product market" },
  { code: "DE", name: "Germany", packs: 30, openings: 3, attribution: "Publisher country" },
  { code: "FR", name: "France", packs: 200, openings: 1, attribution: "Opening location" },
];

describe("Overview chart projections", () => {
  it("uses published map cells and preserves their attribution without changing counts", () => {
    const projected = overviewRows(DEMO_PUBLIC_DATA.mapCells);
    expect(projected).toHaveLength(DEMO_PUBLIC_DATA.mapCells.length);
    expect(projected[0]?.packs).toBe(DEMO_PUBLIC_DATA.mapCells[0]?.packsObserved);
    expect(projected[0]?.openings).toBe(DEMO_PUBLIC_DATA.mapCells[0]?.openings);
    expect(projected[0]).not.toHaveProperty("hitRate");
  });
  it("sorts by the selected count without mutating the snapshot", () => {
    expect(rankCoverage(rows, "packs").map((row) => row.code)).toEqual(["AU", "FR", "DE", "JP"]);
    expect(rankCoverage(rows, "openings").map((row) => row.code)).toEqual(["JP", "DE", "AU", "FR"]);
    expect(rows.map((row) => row.code)).toEqual(["AU", "JP", "DE", "FR"]);
  });
  it("combines name/code search with exact nonoverlapping pack bands", () => {
    expect(rankCoverage(rows, "packs", " jp ", "small").map((row) => row.code)).toEqual(["JP"]);
    expect(rankCoverage(rows, "packs", "JAPAN", "large")).toEqual([]);
    expect(coverageDistribution(rows).map((band) => band.count)).toEqual([1, 1, 1, 1]);
    expect(coverageDistribution([]).map((band) => band.count)).toEqual([0, 0, 0, 0]);
  });
  it("keeps missing and explicit zero unknown-location coverage distinct", () => {
    const base = { ...DEMO_PUBLIC_DATA.observations, observedPacks: 100, completeOpenings: 10 };
    expect(volumeSplit({ ...base, unknownLocation: undefined }, "packs")).toBeNull();
    expect(volumeSplit({ ...base, unknownLocation: null }, "packs")).toEqual({ total: 100, attributed: 100, unknown: 0 });
  });
  it("uses global totals and the explicit unknown bucket, not a sum of country rows", () => {
    const observations = { ...DEMO_PUBLIC_DATA.observations, observedPacks: 100, completeOpenings: 10, unknownLocation: { packsObserved: 90, openings: 7, independentSources: 1, updatedAt: DEMO_PUBLIC_DATA.generatedAt } };
    expect(volumeSplit(observations, "packs")).toEqual({ total: 100, attributed: 10, unknown: 90 });
    expect(volumeSplit(observations, "openings")).toEqual({ total: 10, attributed: 3, unknown: 7 });
    expect(volumeSplit({ ...observations, observedPacks: 89 }, "packs")).toBeNull();
    expect(volumeSplit({ ...observations, observedPacks: 0 }, "packs")).toBeNull();
  });
  it("maps log-scale endpoints without NaN or division by zero", () => {
    expect(logPosition(0, 0)).toBe(0);
    expect(logPosition(1000, 1000)).toBe(1);
    expect(logPosition(10, 1000)).toBeGreaterThan(0);
    expect(logPosition(10, 1000)).toBeLessThan(1);
  });
});
