const individualPackDisclaimer =
  "Observed results do not guarantee the contents of any individual pack, box, product, batch or store purchase.";
const batchDisclaimer =
  "A batch-level observation cannot predict the contents of an individual pack.";
const footerDisclaimer =
  "Pokecrack is an unofficial research dashboard and is not affiliated with, endorsed by, or sponsored by The Pokémon Company, Nintendo, Game Freak or Creatures.";
const projectDescription =
  "An unofficial data dashboard for observed Pokémon TCG pull activity across sets, products, regions, retailers and visible batches.";
const projectScope =
  "Free, personal, experimental and non-commercial; English-language observations of physical Pokémon TCG Booster Boxes, ETBs and Booster Bundles in Australia only.";

export const BRAND = {
  name: "Pokecrack",
  shortName: "PKCRK",
  tagline: "Crack open the data behind every pack.",
  description: projectDescription,
  scope: projectScope,
  observationDisclaimer:
    "Observed pack-opening data describes documented openings only. It does not predict future pulls, product quality, retailer performance, or individual outcomes.",
  individualPackDisclaimer,
  batchDisclaimer,
  footerDisclaimer,
  unofficialNotice: footerDisclaimer,
  demoNotice:
    "Demo data is deterministic, synthetic, Australia-only, and illustrative. It is not a claim about real products, regions, retailers, or batches.",
  copyright: "Data for research and community education only.",
  defaultSiteUrl: "https://pokecrack.example",
} as const;

export type Brand = typeof BRAND;
