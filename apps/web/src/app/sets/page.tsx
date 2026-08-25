import React from "react";
import type { Metadata } from "next";

import { SetsView } from "@/components/dashboard/public-views";
import { PublicUnavailable } from "@/components/ui/dashboard-ui";
import { loadDashboard } from "../_lib/dashboard";
import { createPageMetadata } from "../_lib/metadata";
import { filterAndSortSets, normalizeSearchValue, normalizeSetSort } from "../_lib/sets-query";

export const revalidate = 900;

export const metadata: Metadata = createPageMetadata("Set aggregates", "Observed sample sizes, rates, intervals and signal states across tracked sets.", "/sets");

type SearchParams = Promise<{ q?: string | string[]; sort?: string | string[] }>;

export default async function SetsPage({ searchParams }: { searchParams: SearchParams }) {
  const [result, queryParams] = await Promise.all([loadDashboard(), searchParams]);
  if (result.status === "unavailable") return <PublicUnavailable title="Set data is unavailable" message={result.message} code={result.code} />;
  const query = normalizeSearchValue(queryParams.q);
  const sort = normalizeSetSort(queryParams.sort);
  return <SetsView data={result.data} sets={filterAndSortSets(result.data.sets, query, sort)} query={query} sort={sort} synthetic={result.synthetic} />;
}
