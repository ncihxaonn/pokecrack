import React from "react";
import type { Metadata } from "next";
import { notFound } from "next/navigation";

import { SetDetailView } from "@/components/dashboard/public-views";
import { PublicUnavailable } from "@/components/ui/dashboard-ui";
import { loadDashboard } from "../../_lib/dashboard";
import { createPageMetadata } from "../../_lib/metadata";

type Props = { params: Promise<{ slug: string }> };

export const revalidate = 900;

export async function generateMetadata({ params }: Props): Promise<Metadata> {
  const [{ slug }, result] = await Promise.all([params, loadDashboard()]);
  if (result.status === "unavailable") return createPageMetadata("Set data unavailable", result.message, "/sets", { index: false });
  const set = result.data.sets.find((candidate) => candidate.slug === slug);
  if (!set) notFound();
  return createPageMetadata(set.name, `Observed sample summary for ${set.name}, including interval, sample size and signal state.`, `/sets/${set.slug}`);
}

export default async function SetPage({ params }: Props) {
  const [{ slug }, result] = await Promise.all([params, loadDashboard()]);
  if (result.status === "unavailable") return <PublicUnavailable title="Set data is unavailable" message={result.message} code={result.code} />;
  const set = result.data.sets.find((candidate) => candidate.slug === slug);
  if (!set) notFound();
  return <SetDetailView data={result.data} set={set} synthetic={result.synthetic} />;
}
