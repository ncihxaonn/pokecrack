import React from "react";
import type { Metadata } from "next";

import { RegionsView } from "@/components/dashboard/public-views";
import { PublicUnavailable } from "@/components/ui/dashboard-ui";
import { loadDashboard } from "../_lib/dashboard";
import { createPageMetadata } from "../_lib/metadata";

export const revalidate = 900;

export const metadata: Metadata = createPageMetadata("Regional observations", "Legacy Australian regional detail alongside the worldwide country-level dashboard.", "/regions");

export default async function RegionsPage() {
  const result = await loadDashboard();
  if (result.status === "unavailable") return <PublicUnavailable title="Region data is unavailable" message={result.message} code={result.code} />;
  return <RegionsView data={result.data} synthetic={result.synthetic} />;
}
