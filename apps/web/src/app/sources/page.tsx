import React from "react";
import type { Metadata } from "next";

import { SourcesView } from "@/components/dashboard/public-views";
import { PublicUnavailable } from "@/components/ui/dashboard-ui";
import { loadOperationalDashboard } from "../_lib/dashboard";
import { createPageMetadata } from "../_lib/metadata";

// Source health is computed against the database clock. Do not let the page
// itself or the platform CDN reuse a stale `operational` response.
export const dynamic = "force-dynamic";
export const revalidate = 0;

export const metadata: Metadata = createPageMetadata("Sources", "Public source classes, collection boundaries and aggregate availability.", "/sources");

export default async function SourcesPage() {
  const result = await loadOperationalDashboard();
  if (result.status === "unavailable") return <PublicUnavailable title="Source data is unavailable" message={result.message} code={result.code} />;
  return <SourcesView data={result.data} synthetic={result.synthetic} />;
}
