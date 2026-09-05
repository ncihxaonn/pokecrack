export type WorldHeatMetric = "coverage" | "delta" | "rate";

export function normalizeWorldHeatMetric(
  value: string | string[] | undefined,
): WorldHeatMetric | undefined {
  if (typeof value !== "string") return undefined;
  return value === "coverage" || value === "delta" || value === "rate"
    ? value
    : undefined;
}

export function defaultWorldHeatMetric(countriesWithPublishedRate: number): WorldHeatMetric {
  return countriesWithPublishedRate === 0 ? "coverage" : "rate";
}
