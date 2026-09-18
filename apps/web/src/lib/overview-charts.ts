import type { CountryMapCell, ObservationReadiness } from "@/data/types";
import { formatCoverageAttribution } from "./coverage-attribution";

export type CoverageMetric = "packs" | "openings";
export type CoverageRow = {
  code: string;
  name: string;
  packs: number;
  openings: number;
  attribution: string;
};

export const coverageBands = [
  { id: "small", label: "1–29 packs", min: 1, max: 29 },
  { id: "medium", label: "30–199 packs", min: 30, max: 199 },
  { id: "large", label: "200–999 packs", min: 200, max: 999 },
  { id: "largest", label: "1,000+ packs", min: 1000, max: Infinity },
] as const;

export type CoverageBand = "all" | typeof coverageBands[number]["id"];

export function overviewRows(cells: readonly CountryMapCell[]): CoverageRow[] {
  return cells.map((cell) => ({
    code: cell.countryCode,
    name: cell.countryName,
    packs: cell.packsObserved,
    openings: cell.openings,
    attribution: formatCoverageAttribution(cell.coverageAttributionBases),
  }));
}

export function rankCoverage(rows: readonly CoverageRow[], metric: CoverageMetric, query = "", band: CoverageBand = "all") {
  const search = query.trim().toLocaleLowerCase("en-AU");
  const range = coverageBands.find((item) => item.id === band);
  return rows.filter((row) =>
    row[metric] > 0 &&
    (!search || `${row.name} ${row.code}`.toLocaleLowerCase("en-AU").includes(search)) &&
    (!range || (row.packs >= range.min && row.packs <= range.max)),
  ).sort((a, b) => b[metric] - a[metric] || a.name.localeCompare(b.name, "en-AU"));
}

// Use the explicit global unknown-location bucket. Never infer a new worldwide
// denominator by adding potentially overlapping geographic attributions.
export function volumeSplit(observations: ObservationReadiness, metric: CoverageMetric) {
  const total = metric === "packs" ? observations.observedPacks : observations.completeOpenings;
  if (observations.unknownLocation === undefined) return null;
  const unknown = observations.unknownLocation === null ? 0
    : metric === "packs" ? observations.unknownLocation.packsObserved : observations.unknownLocation.openings;
  if (!Number.isSafeInteger(total) || !Number.isSafeInteger(unknown) || total <= 0 || unknown < 0 || unknown > total) return null;
  return { total, attributed: total - unknown, unknown };
}

export function coverageDistribution(rows: readonly CoverageRow[]) {
  return coverageBands.map((band) => ({
    ...band,
    count: rows.filter((row) => row.packs >= band.min && row.packs <= band.max).length,
  }));
}

export function logPosition(value: number, maximum: number) {
  return Math.log10(1 + Math.max(0, value)) / Math.log10(1 + Math.max(1, maximum));
}
