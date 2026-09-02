import React from "react";
import type { Metadata } from "next";

import { StatusView } from "@/components/dashboard/public-views";
import { PublicUnavailable } from "@/components/ui/dashboard-ui";
import { loadOperationalDashboard } from "../_lib/dashboard";
import { createPageMetadata } from "../_lib/metadata";

// Service/source health is computed against the database clock. Do not let
// the page itself or the platform CDN reuse a stale `operational` response.
export const dynamic = "force-dynamic";
export const revalidate = 0;

export const metadata: Metadata = createPageMetadata("System status", "Public aggregate service availability and snapshot freshness.", "/status");

export default async function StatusPage() {
  const result = await loadOperationalDashboard();
  if (result.status === "unavailable") return <PublicUnavailable title="Public status is unavailable" message={result.message} code={result.code} />;
  return <StatusView data={result.data} synthetic={result.synthetic} />;
}
