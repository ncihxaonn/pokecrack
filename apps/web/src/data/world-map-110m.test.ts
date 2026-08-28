import { describe, expect, it } from "vitest";

import mapData from "./world-map-110m.json";
import { isIsoAlpha2 } from "./iso-alpha2";

describe("Natural Earth world-map artifact", () => {
  it("pins the reviewed source, projection, and expected feature counts", () => {
    expect(mapData.source.version).toBe("5.1.1");
    expect(mapData.source.projection).toBe("Robinson");
    expect(mapData.source.mapshaperVersion).toBe("0.7.55");
    expect(mapData.source.license).toBe("Public domain");
    expect(mapData.countries).toHaveLength(177);
    expect(mapData.tinyCountries).toHaveLength(37);
    expect(mapData.viewBox).toBe("0 0 1000 505");
  });

  it("joins only official ISO alpha-2 codes and keeps disputed geometries neutral", () => {
    const codedFeatures = [...mapData.countries, ...mapData.tinyCountries]
      .filter((feature) => feature.countryCode !== null);
    expect(codedFeatures.every((feature) => isIsoAlpha2(feature.countryCode))).toBe(true);
    expect(mapData.countries.filter((feature) => feature.countryCode === null).map((feature) => feature.countryName)).toEqual([
      "Turkish Republic of Northern Cyprus",
      "Somaliland",
      "Kosovo",
    ]);
  });

  it("keeps every tiny-country marker inside the exported viewport", () => {
    for (const point of mapData.tinyCountries) {
      expect(point.x).toBeGreaterThanOrEqual(0);
      expect(point.x).toBeLessThanOrEqual(1000);
      expect(point.y).toBeGreaterThanOrEqual(0);
      expect(point.y).toBeLessThanOrEqual(505);
    }
  });
});
