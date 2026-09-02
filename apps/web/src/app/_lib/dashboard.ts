import { unstable_cache } from "next/cache";
import { cache } from "react";

import { getDashboardData } from "@/data/server";

const cachedDashboard = unstable_cache(
  getDashboardData,
  ["public-dashboard-v3-coverage-v2-social-v4-live60"],
  {
    revalidate: 60,
    tags: ["public-dashboard"],
  },
);

export const loadDashboard = cache(cachedDashboard);

// Operational pages must evaluate the database clock on every request. React's
// cache only deduplicates calls within one render; unlike `cachedDashboard`, it
// does not create a Next/Vercel persistent cache entry. The public RPCs then
// calculate social freshness against the request-time statement timestamp.
export const loadOperationalDashboard = cache(getDashboardData);
