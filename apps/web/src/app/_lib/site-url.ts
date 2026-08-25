import { BRAND } from "@/config/brand";

export function getSiteUrl(): string {
  const configured = process.env.NEXT_PUBLIC_SITE_URL?.trim();
  try {
    return new URL(configured || BRAND.defaultSiteUrl).toString().replace(/\/$/, "");
  } catch {
    return BRAND.defaultSiteUrl;
  }
}

export function absoluteUrl(path: string): string {
  return new URL(path, `${getSiteUrl()}/`).toString();
}
