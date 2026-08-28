import type { Metadata, Viewport } from "next";
import type { ReactNode } from "react";

import { BRAND } from "@/config/brand";
import { SiteFooter, SiteHeader } from "./_components/site-chrome";
import "./globals.css";

const configuredSiteUrl = process.env.NEXT_PUBLIC_SITE_URL ?? BRAND.defaultSiteUrl;
const siteUrl = configuredSiteUrl.endsWith("/") ? configuredSiteUrl.slice(0, -1) : configuredSiteUrl;

export const metadata: Metadata = {
  metadataBase: new URL(siteUrl),
  title: {
    default: BRAND.name,
    template: `%s · ${BRAND.name}`,
  },
  description: BRAND.description,
  applicationName: BRAND.name,
  category: "education",
  alternates: { canonical: "/" },
  openGraph: {
    type: "website",
    url: "/",
    siteName: BRAND.name,
    title: BRAND.name,
    description: BRAND.description,
    locale: "en_AU",
    images: [{ url: "/opengraph-image", width: 1200, height: 630, alt: `${BRAND.name} observed activity dashboard` }],
  },
  twitter: {
    card: "summary_large_image",
    title: BRAND.name,
    description: BRAND.description,
    images: ["/opengraph-image"],
  },
  robots: { index: true, follow: true },
  icons: { icon: "/icon.svg" },
};

export const viewport: Viewport = {
  colorScheme: "light",
  themeColor: "#f3f4f7",
  width: "device-width",
  initialScale: 1,
};

export default function RootLayout({ children }: Readonly<{ children: ReactNode }>) {
  return (
    <html lang="en-AU">
      <body>
        <a className="skip-link" href="#main-content">Skip to content</a>
        <SiteHeader />
        <main id="main-content" tabIndex={-1}>{children}</main>
        <SiteFooter />
      </body>
    </html>
  );
}
