import React from "react";
import type { Metadata } from "next";

import { RetailersView } from "@/components/dashboard/public-views";
import { PublicUnavailable } from "@/components/ui/dashboard-ui";
import { loadDashboard } from "../_lib/dashboard";
import { createPageMetadata } from "../_lib/metadata";

export const revalidate = 900;

export const metadata: Metadata = createPageMetadata("Retailer observations", "Attributed retailer sample coverage and aggregate observations without rankings or causal claims.", "/retailers");

export default async function RetailersPage() {
  const result = await loadDashboard();
  if (result.status === "unavailable") return <PublicUnavailable title="Retailer data is unavailable" message={result.message} code={result.code} />;
  return <RetailersView data={result.data} synthetic={result.synthetic} />;
}
