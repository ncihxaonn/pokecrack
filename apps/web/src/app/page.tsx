import React from "react";

import { BRAND } from "@/config/brand";
import { HomeView } from "@/components/dashboard/home-view";
import { PublicUnavailable } from "@/components/ui/dashboard-ui";
import { JsonLd } from "./_components/json-ld";
import { loadDashboard } from "./_lib/dashboard";

export const revalidate = 900;

export default async function HomePage() {
  const result = await loadDashboard();
  if (result.status === "unavailable") {
    return <PublicUnavailable title="Dashboard data is unavailable" message={result.message} code={result.code} />;
  }

  const siteUrl = process.env.NEXT_PUBLIC_SITE_URL ?? BRAND.defaultSiteUrl;
  const website = { "@context": "https://schema.org", "@type": "WebSite", name: BRAND.name, url: siteUrl, description: BRAND.description, inLanguage: "en-AU" };
  const catalog = { "@context": "https://schema.org", "@type": "DataCatalog", name: `${BRAND.name} observed activity catalog`, description: BRAND.description, url: siteUrl, spatialCoverage: "Australia", dataset: { "@id": `${siteUrl}/#dataset` } };
  const dataset = { "@context": "https://schema.org", "@type": "Dataset", "@id": `${siteUrl}/#dataset`, name: "Observed Pokémon TCG pack-opening activity", description: BRAND.observationDisclaimer, spatialCoverage: "Australia", temporalCoverage: `../${result.data.generatedAt.slice(0, 10)}`, isAccessibleForFree: true, creator: { "@type": "Organization", name: BRAND.name }, url: siteUrl };

  return <><JsonLd data={website} /><JsonLd data={catalog} /><JsonLd data={dataset} /><HomeView data={result.data} synthetic={result.synthetic} /></>;
}
