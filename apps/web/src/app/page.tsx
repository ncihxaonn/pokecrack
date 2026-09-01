import React from "react";

import { BRAND } from "@/config/brand";
import { HomeView } from "@/components/dashboard/home-view";
import { PublicUnavailable } from "@/components/ui/dashboard-ui";
import { JsonLd } from "./_components/json-ld";
import { loadDashboard } from "./_lib/dashboard";
import { defaultWorldHeatMetric, normalizeWorldHeatMetric } from "./_lib/world-map-query";

// Keep the route shell in step with the one-minute dashboard data cache.
export const revalidate = 60;

type SearchParams = Promise<{ metric?: string | string[] }>;

export default async function HomePage({ searchParams }: { searchParams: SearchParams }) {
  const [result, queryParams] = await Promise.all([loadDashboard(), searchParams]);
  if (result.status === "unavailable") {
    return <PublicUnavailable title="Dashboard data is unavailable" message={result.message} code={result.code} />;
  }

  const siteUrl = process.env.NEXT_PUBLIC_SITE_URL ?? BRAND.defaultSiteUrl;
  const website = { "@context": "https://schema.org", "@type": "WebSite", name: BRAND.name, url: siteUrl, description: BRAND.description, inLanguage: "en" };
  const catalog = { "@context": "https://schema.org", "@type": "DataCatalog", name: `${BRAND.name} global observed activity catalog`, description: BRAND.description, url: siteUrl, spatialCoverage: "Worldwide", dataset: { "@id": `${siteUrl}/#dataset` } };
  const dataset = { "@context": "https://schema.org", "@type": "Dataset", "@id": `${siteUrl}/#dataset`, name: "Worldwide observed Pokémon TCG pack-opening activity", description: BRAND.observationDisclaimer, spatialCoverage: "Worldwide", temporalCoverage: `../${result.data.generatedAt.slice(0, 10)}`, isAccessibleForFree: true, creator: { "@type": "Organization", name: BRAND.name }, url: siteUrl };

  const worldMetric = normalizeWorldHeatMetric(queryParams.metric)
    ?? defaultWorldHeatMetric(result.data.observations.countriesWithPublishedRate);

  return <><JsonLd data={website} /><JsonLd data={catalog} /><JsonLd data={dataset} /><HomeView data={result.data} synthetic={result.synthetic} worldMetric={worldMetric} /></>;
}
