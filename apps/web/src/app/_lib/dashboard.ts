import { unstable_cache } from "next/cache";
import { cache } from "react";

import { getDashboardData } from "@/data/server";

const cachedDashboard = unstable_cache(
  getDashboardData,
  ["public-dashboard-v3-coverage-v1-social-v2-live60"],
  {
    revalidate: 60,
    tags: ["public-dashboard"],
  },
);

export const loadDashboard = cache(cachedDashboard);
