import React from "react";
import type { Metadata } from "next";

import { SourcesView } from "@/components/dashboard/public-views";
import { PublicUnavailable } from "@/components/ui/dashboard-ui";
import { loadDashboard } from "../_lib/dashboard";
import { createPageMetadata } from "../_lib/metadata";

export const revalidate = 900;

export const metadata: Metadata = createPageMetadata("Sources", "Public source classes, collection boundaries and aggregate availability.", "/sources");

export default async function SourcesPage() {
  const result = await loadDashboard();
  if (result.status === "unavailable") return <PublicUnavailable title="Source data is unavailable" message={result.message} code={result.code} />;
  return <SourcesView data={result.data} synthetic={result.synthetic} />;
}
