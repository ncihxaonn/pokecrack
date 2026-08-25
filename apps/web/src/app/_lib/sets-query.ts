import type { SetMetric } from "@/data/types";

export type SetSort = "name" | "packs" | "rate" | "release";

export function normalizeSearchValue(value: string | string[] | undefined): string {
  return (Array.isArray(value) ? value[0] : value)?.trim() ?? "";
}

export function normalizeSetSort(value: string | string[] | undefined): SetSort {
  const candidate = Array.isArray(value) ? value[0] : value;
  return candidate === "name" || candidate === "packs" || candidate === "rate" || candidate === "release"
    ? candidate
    : "packs";
}

export function filterAndSortSets(
  sets: readonly SetMetric[],
  query: string,
  sort: SetSort,
): SetMetric[] {
  const normalizedQuery = query.trim().toLocaleLowerCase("en-AU");
  const filtered = normalizedQuery
    ? sets.filter((set) => `${set.name} ${set.series}`.toLocaleLowerCase("en-AU").includes(normalizedQuery))
    : [...sets];

  return filtered.sort((left, right) => {
    if (sort === "name") return left.name.localeCompare(right.name, "en-AU");
    if (sort === "release") return right.releaseDate.localeCompare(left.releaseDate);
    if (sort === "rate") {
      if (left.hitRate === null) return right.hitRate === null ? left.name.localeCompare(right.name) : 1;
      if (right.hitRate === null) return -1;
      return right.hitRate - left.hitRate || right.packsObserved - left.packsObserved;
    }
    return right.packsObserved - left.packsObserved || left.name.localeCompare(right.name, "en-AU");
  });
}
