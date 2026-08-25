import { unstable_cache } from "next/cache";
import { cache } from "react";

import { getDashboardData } from "@/data/server";

const cachedDashboard = unstable_cache(getDashboardData, ["public-dashboard-v1"], {
  revalidate: 900,
  tags: ["public-dashboard"],
});

export const loadDashboard = cache(cachedDashboard);
