import { describe, expect, it } from "vitest";

import { DEMO_PUBLIC_DATA } from "@/data/demo";
import { buildRegionHeatRows } from "./region-heatmap";
import { buildAustraliaRegionGeoJson, REGION_TONE_COLOURS, regionHeatColour } from "./regional-map-data";

describe("buildAustraliaRegionGeoJson", () => {
  it("colours published states and leaves states without data neutral", () => {
    const geoJson = buildAustraliaRegionGeoJson(buildRegionHeatRows(DEMO_PUBLIC_DATA.regions, "rate"));

    expect(geoJson.features).toHaveLength(8);
    expect(geoJson.features.filter((feature) => feature.properties.has_data)).toHaveLength(4);
    expect(geoJson.features.find((feature) => feature.id === "2")?.properties).toMatchObject({
      fill_color: REGION_TONE_COLOURS.hot,
      has_data: true,
      region_slug: "au-vic-melbourne",
      tone: "hot",
    });
    expect(geoJson.features.find((feature) => feature.id === "6")?.properties).toMatchObject({
      fill_color: REGION_TONE_COLOURS.withheld,
      has_data: false,
      metric_value: null,
      region_slug: null,
      tone: "withheld",
    });
  });

  it("does not mutate the generated ABS boundary source between metrics", () => {
    const rate = buildAustraliaRegionGeoJson(buildRegionHeatRows(DEMO_PUBLIC_DATA.regions, "rate"));
    const packs = buildAustraliaRegionGeoJson(buildRegionHeatRows(DEMO_PUBLIC_DATA.regions, "packs"));

    expect(rate.features.find((feature) => feature.id === "1")?.properties.metric_value).toBe(0.149);
    expect(packs.features.find((feature) => feature.id === "1")?.properties.metric_value).toBe(1_544);
    expect(rate.features[0]?.geometry).toBe(packs.features[0]?.geometry);
  });

  it("uses a continuous blue-to-violet-to-pink regional scale", () => {
    expect(regionHeatColour(0)).toBe(REGION_TONE_COLOURS.cool);
    expect(regionHeatColour(0.5)).toBe(REGION_TONE_COLOURS.mid);
    expect(regionHeatColour(1)).toBe(REGION_TONE_COLOURS.hot);
    expect(regionHeatColour(0.25)).not.toBe(REGION_TONE_COLOURS.cool);
  });
});
