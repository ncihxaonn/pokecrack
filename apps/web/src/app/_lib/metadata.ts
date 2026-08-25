import type { Metadata } from "next";

import { BRAND } from "@/config/brand";

export function createPageMetadata(
  title: string,
  description: string,
  path: string,
  options: { index?: boolean } = {},
): Metadata {
  const index = options.index ?? true;
  return {
    title,
    description,
    alternates: { canonical: path },
    openGraph: {
      type: "website",
      url: path,
      siteName: BRAND.name,
      title: `${title} · ${BRAND.name}`,
      description,
      images: [{ url: "/opengraph-image", width: 1200, height: 630, alt: `${title} on ${BRAND.name}` }],
    },
    twitter: {
      card: "summary_large_image",
      title: `${title} · ${BRAND.name}`,
      description,
      images: ["/opengraph-image"],
    },
    robots: { index, follow: index },
  };
}

export function unavailableMetadata(entityType: string): Metadata {
  return createPageMetadata(
    `${entityType} data unavailable`,
    `The live ${entityType.toLowerCase()} aggregate is currently unavailable.`,
    `/${entityType.toLowerCase()}s`,
    { index: false },
  );
}
