import type { DashboardResult } from "@/data/resolver";

export const DASHBOARD_CACHE_TTL_SECONDS = 60;

export interface DashboardCacheEntry {
  readonly cachedAt: number;
  readonly result: DashboardResult;
}

// Next's background revalidation may return a stale entry. Public evidence
// must not depend on that background update completing to become visible.
export async function resolveFreshDashboard(
  entry: DashboardCacheEntry,
  loadFresh: () => Promise<DashboardResult>,
  now = Date.now(),
): Promise<DashboardResult> {
  const age = now - entry.cachedAt;
  if (Number.isFinite(age) && age >= 0 && age < DASHBOARD_CACHE_TTL_SECONDS * 1_000) {
    return entry.result;
  }
  return loadFresh();
}
