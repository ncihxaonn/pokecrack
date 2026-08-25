import React from "react";
import type { Metadata } from "next";

import { StatusView } from "@/components/dashboard/public-views";
import { PublicUnavailable } from "@/components/ui/dashboard-ui";
import { loadDashboard } from "../_lib/dashboard";
import { createPageMetadata } from "../_lib/metadata";

export const revalidate = 900;

export const metadata: Metadata = createPageMetadata("System status", "Public aggregate service availability and snapshot freshness.", "/status");

export default async function StatusPage() {
  const result = await loadDashboard();
  if (result.status === "unavailable") return <PublicUnavailable title="Public status is unavailable" message={result.message} code={result.code} />;
  return <StatusView data={result.data} synthetic={result.synthetic} />;
}
