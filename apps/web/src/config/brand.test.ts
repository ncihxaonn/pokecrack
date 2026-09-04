import { describe, expect, it } from "vitest";

import { BRAND } from "./brand";

describe("BRAND", () => {
  it("centralizes the public identity and observation disclaimer", () => {
    expect(BRAND.name).toBe("Pokecrack");
    expect(BRAND.tagline).toBe("Crack open the data behind every pack.");
    expect(BRAND.description).toBe(
      "An unofficial global dashboard for country and product-market Pokémon TCG coverage buckets, set-catalog coverage and conservative qualifying-hit estimates.",
    );
    expect(BRAND.scope).toMatch(/free.*experimental.*non-commercial/i);
    expect(BRAND.scope).toMatch(/worldwide/i);
    expect(BRAND.observationDisclaimer).toMatch(/observed/i);
    expect(BRAND.observationDisclaimer).toMatch(/does not predict/i);
    expect(BRAND.unofficialNotice).toMatch(/unofficial/i);
    expect(BRAND.individualPackDisclaimer).toBe(
      "Observed results do not guarantee the contents of any individual pack, box, product, batch or store purchase.",
    );
    expect(BRAND.batchDisclaimer).toBe(
      "A batch-level observation cannot predict the contents of an individual pack.",
    );
    expect(BRAND.footerDisclaimer).toBe(
      "Pokecrack is an unofficial research dashboard and is not affiliated with, endorsed by, or sponsored by The Pokémon Company, Nintendo, Game Freak or Creatures.",
    );
  });

  it("contains no commercial monetization language", () => {
    const copy = JSON.stringify(BRAND).toLowerCase();
    expect(copy).not.toMatch(/subscribe now|buy now|advertising|sponsored listing/);
  });
});
