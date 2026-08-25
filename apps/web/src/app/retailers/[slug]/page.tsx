import React from "react";
import type { Metadata } from "next";
import { notFound } from "next/navigation";

import { RetailerDetailView } from "@/components/dashboard/public-views";
import { PublicUnavailable } from "@/components/ui/dashboard-ui";
import { loadDashboard } from "../../_lib/dashboard";
import { createPageMetadata } from "../../_lib/metadata";

type Props = { params: Promise<{ slug: string }> };

export const revalidate = 900;

export async function generateMetadata({ params }: Props): Promise<Metadata> {
  const [{ slug }, result] = await Promise.all([params, loadDashboard()]);
  if (result.status === "unavailable") return createPageMetadata("Retailer data unavailable", result.message, "/retailers", { index: false });
  const retailer = result.data.retailers.find((candidate) => candidate.slug === slug);
  if (!retailer) notFound();
  return createPageMetadata(retailer.name, `Attributed sample coverage and aggregate observations for ${retailer.name}.`, `/retailers/${retailer.slug}`);
}

export default async function RetailerPage({ params }: Props) {
  const [{ slug }, result] = await Promise.all([params, loadDashboard()]);
  if (result.status === "unavailable") return <PublicUnavailable title="Retailer data is unavailable" message={result.message} code={result.code} />;
  const retailer = result.data.retailers.find((candidate) => candidate.slug === slug);
  if (!retailer) notFound();
  return <RetailerDetailView data={result.data} retailer={retailer} synthetic={result.synthetic} />;
}
