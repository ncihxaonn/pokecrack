import type { MetadataRoute } from "next";

import { absoluteUrl, getSiteUrl } from "./_lib/site-url";

export default function robots(): MetadataRoute.Robots {
  return {
    rules: [{
      userAgent: "*",
      allow: "/",
      disallow: ["/admin", "/admin/", "/api/internal", "/api/internal/"],
    }],
    sitemap: absoluteUrl("/sitemap.xml"),
    host: getSiteUrl(),
  };
}
