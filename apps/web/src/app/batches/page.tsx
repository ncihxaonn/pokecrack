import React from "react";
import type { Metadata } from "next";

import { BatchesView } from "@/components/dashboard/public-views";
import { PublicUnavailable } from "@/components/ui/dashboard-ui";
import { loadDashboard } from "../_lib/dashboard";
import { createPageMetadata } from "../_lib/metadata";

export const revalidate = 900;

export const metadata: Metadata = createPageMetadata("Batch observations", "Exploratory aggregates for visible batch or lot labels in documented observations.", "/batches");

export default async function BatchesPage() {
  const result = await loadDashboard();
  if (result.status === "unavailable") return <PublicUnavailable title="Batch data is unavailable" message={result.message} code={result.code} />;
  return <BatchesView data={result.data} synthetic={result.synthetic} />;
}
