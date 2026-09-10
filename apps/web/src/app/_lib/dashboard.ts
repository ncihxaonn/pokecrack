import { unstable_cache } from "next/cache";
import { cache } from "react";

import { getDashboardData } from "@/data/server";
import { DASHBOARD_CACHE_TTL_SECONDS, resolveFreshDashboard } from "./dashboard-freshness";

const cachedDashboard = unstable_cache(
  async () => {
    const result = await getDashboardData();
    return { result, cachedAt: Date.now() };
  },
  ["public-dashboard-v3-coverage-v4-source-coverage-v1-social-v4-live60-hard-age-v1"],
  {
    revalidate: DASHBOARD_CACHE_TTL_SECONDS,
    tags: ["public-dashboard"],
  },
);

export const loadDashboard = cache(async () =>
  resolveFreshDashboard(await cachedDashboard(), getDashboardData),
);

// Operational pages must evaluate the database clock on every request. React's
// cache only deduplicates calls within one render; unlike `cachedDashboard`, it
// does not create a Next/Vercel persistent cache entry. The public RPCs then
// calculate social freshness against the request-time statement timestamp.
export const loadOperationalDashboard = cache(getDashboardData);
