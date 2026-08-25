import React from "react";
import type { Metadata } from "next";

import { MethodologyView } from "@/components/dashboard/public-views";
import { PublicUnavailable } from "@/components/ui/dashboard-ui";
import { loadDashboard } from "../_lib/dashboard";
import { createPageMetadata } from "../_lib/metadata";

export const revalidate = 900;

export const metadata: Metadata = createPageMetadata("Methodology", "Eligibility, denominators, evidence tiers, interval estimates and exploratory signal thresholds.", "/methodology");

export default async function MethodologyPage() {
  const result = await loadDashboard();
  if (result.status === "unavailable") return <PublicUnavailable title="Methodology snapshot is unavailable" message={result.message} code={result.code} />;
  return <MethodologyView data={result.data} synthetic={result.synthetic} />;
}
