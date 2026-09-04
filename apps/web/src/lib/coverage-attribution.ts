import type { CoverageAttributionBasis } from "@/data/types";

const coverageAttributionLabels: Record<CoverageAttributionBasis, string> = {
  publisher_country: "Publisher country",
  author_public_residence: "Author public residence",
  product_market: "Product market",
};

export function formatCoverageAttribution(
  bases: readonly CoverageAttributionBasis[] | undefined,
  fallback = "Attribution not provided",
): string {
  if (bases === undefined || bases.length === 0) return fallback;
  return bases.map((basis) => coverageAttributionLabels[basis]).join(" + ");
}

export function sourceNativeLanguageTag(version: string): string | undefined {
  const language = version.split(" · ", 1)[0]?.trim();
  if (
    language === undefined ||
    language === "" ||
    language === "und" ||
    !/^[A-Za-z]{2,3}(?:-[A-Za-z0-9]{2,8})*$/.test(language)
  ) {
    return undefined;
  }
  try {
    return Intl.getCanonicalLocales(language)[0];
  } catch {
    return undefined;
  }
}
