import React from "react";
import type { Metadata } from "next";
import { notFound } from "next/navigation";

import { RegionDetailView } from "@/components/dashboard/public-views";
import { PublicUnavailable } from "@/components/ui/dashboard-ui";
import { loadDashboard } from "../../_lib/dashboard";
import { createPageMetadata } from "../../_lib/metadata";

type Props = { params: Promise<{ slug: string }> };

export const revalidate = 900;

export async function generateMetadata({ params }: Props): Promise<Metadata> {
  const [{ slug }, result] = await Promise.all([params, loadDashboard()]);
  if (result.status === "unavailable") return createPageMetadata("Country data unavailable", result.message, "/regions", { index: false });
  const region = result.data.regions.find((candidate) => candidate.slug === slug);
  if (!region) notFound();
  return createPageMetadata(region.name, `Observed activity coverage and aggregate sample summary for ${region.name}.`, `/regions/${region.slug}`);
}

export default async function RegionPage({ params }: Props) {
  const [{ slug }, result] = await Promise.all([params, loadDashboard()]);
  if (result.status === "unavailable") return <PublicUnavailable title="Country data is unavailable" message={result.message} code={result.code} />;
  const region = result.data.regions.find((candidate) => candidate.slug === slug);
  if (!region) notFound();
  return <RegionDetailView data={result.data} region={region} synthetic={result.synthetic} />;
}
