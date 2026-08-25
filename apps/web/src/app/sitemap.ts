import type { MetadataRoute } from "next";

import { loadDashboard } from "./_lib/dashboard";
import { absoluteUrl } from "./_lib/site-url";

export const revalidate = 900;

const staticRoutes = [
  { path: "/", priority: 1, changeFrequency: "daily" as const },
  { path: "/sets", priority: 0.9, changeFrequency: "daily" as const },
  { path: "/regions", priority: 0.8, changeFrequency: "daily" as const },
  { path: "/retailers", priority: 0.8, changeFrequency: "daily" as const },
  { path: "/batches", priority: 0.8, changeFrequency: "daily" as const },
  { path: "/methodology", priority: 0.7, changeFrequency: "monthly" as const },
  { path: "/sources", priority: 0.6, changeFrequency: "weekly" as const },
  { path: "/status", priority: 0.5, changeFrequency: "hourly" as const },
] as const;

export default async function sitemap(): Promise<MetadataRoute.Sitemap> {
  const base = staticRoutes.map((route) => ({ url: absoluteUrl(route.path), changeFrequency: route.changeFrequency, priority: route.priority }));
  const result = await loadDashboard();
  if (result.status === "unavailable") return base;

  const lastModified = new Date(result.data.generatedAt);
  const detail = [
    ...result.data.sets.filter((item) => item.slug.length > 0).map((item) => ({ url: absoluteUrl(`/sets/${item.slug}`), lastModified, changeFrequency: "weekly" as const, priority: 0.7 })),
    ...result.data.regions.filter((item) => item.slug.length > 0).map((item) => ({ url: absoluteUrl(`/regions/${item.slug}`), lastModified, changeFrequency: "weekly" as const, priority: 0.6 })),
    ...result.data.retailers.filter((item) => item.slug.length > 0).map((item) => ({ url: absoluteUrl(`/retailers/${item.slug}`), lastModified, changeFrequency: "weekly" as const, priority: 0.6 })),
    ...result.data.batches.filter((item) => item.code.length > 0).map((item) => ({ url: absoluteUrl(`/batches/${encodeURIComponent(item.code)}`), lastModified, changeFrequency: "weekly" as const, priority: 0.5 })),
  ];
  return [...base, ...detail];
}
