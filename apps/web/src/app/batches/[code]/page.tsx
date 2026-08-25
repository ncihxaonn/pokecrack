import React from "react";
import type { Metadata } from "next";
import { notFound } from "next/navigation";

import { BatchDetailView } from "@/components/dashboard/public-views";
import { PublicUnavailable } from "@/components/ui/dashboard-ui";
import { loadDashboard } from "../../_lib/dashboard";
import { createPageMetadata } from "../../_lib/metadata";

type Props = { params: Promise<{ code: string }> };

function findBatch(code: string, batches: readonly import("@/data/types").BatchMetric[]) {
  return batches.find((candidate) => candidate.code.toLocaleLowerCase("en-AU") === code.toLocaleLowerCase("en-AU"));
}

export const revalidate = 900;

export async function generateMetadata({ params }: Props): Promise<Metadata> {
  const [{ code }, result] = await Promise.all([params, loadDashboard()]);
  if (result.status === "unavailable") return createPageMetadata("Batch data unavailable", result.message, "/batches", { index: false });
  const batch = findBatch(code, result.data.batches);
  if (!batch) notFound();
  return createPageMetadata(batch.code, `Observed batch-label aggregate for ${batch.setName} in ${batch.region}.`, `/batches/${encodeURIComponent(batch.code)}`);
}

export default async function BatchPage({ params }: Props) {
  const [{ code }, result] = await Promise.all([params, loadDashboard()]);
  if (result.status === "unavailable") return <PublicUnavailable title="Batch data is unavailable" message={result.message} code={result.code} />;
  const batch = findBatch(code, result.data.batches);
  if (!batch) notFound();
  return <BatchDetailView data={result.data} batch={batch} synthetic={result.synthetic} />;
}
