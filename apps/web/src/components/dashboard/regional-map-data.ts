import australiaStateBoundaries from "@/data/australia-state-boundaries.json";
import type { RegionHeatRow } from "./region-heatmap";

export const REGION_TONE_COLOURS = {
  cool: "#3867f4",
  mid: "#7958e8",
  hot: "#ed4e91",
  withheld: "#f7f9fc",
} as const satisfies Readonly<Record<RegionHeatRow["tone"], string>>;

const HEAT_STOPS = [
  { at: 0, rgb: [56, 103, 244] },
  { at: 0.5, rgb: [121, 88, 232] },
  { at: 1, rgb: [237, 78, 145] },
] as const;

function toHex(value: number): string {
  return Math.round(value).toString(16).padStart(2, "0");
}

export function regionHeatColour(normalized: number | null): string {
  if (normalized === null) return REGION_TONE_COLOURS.withheld;
  const value = Math.min(1, Math.max(0, normalized));
  const lower = value <= HEAT_STOPS[1].at ? HEAT_STOPS[0] : HEAT_STOPS[1];
  const upper = value <= HEAT_STOPS[1].at ? HEAT_STOPS[1] : HEAT_STOPS[2];
  const progress = (value - lower.at) / (upper.at - lower.at);
  const channels = lower.rgb.map((channel, index) => (
    channel + (upper.rgb[index]! - channel) * progress
  ));
  return `#${channels.map(toHex).join("")}`;
}

interface AustraliaBoundaryProperties {
  readonly state_code_2021: string;
  readonly state_name_2021: string;
}

interface AustraliaBoundaryFeature {
  readonly type: "Feature";
  readonly id: string;
  readonly properties: AustraliaBoundaryProperties;
  readonly geometry: {
    readonly type: "Polygon";
    readonly coordinates: readonly (readonly (readonly number[])[])[];
  };
}

interface AustraliaBoundaryCollection {
  readonly type: "FeatureCollection";
  readonly name: string;
  readonly source: string;
  readonly note: string;
  readonly features: readonly AustraliaBoundaryFeature[];
}

export interface AustraliaRegionFeatureCollection {
  readonly type: "FeatureCollection";
  readonly name: string;
  readonly source: string;
  readonly note: string;
  readonly features: readonly (AustraliaBoundaryFeature & {
    readonly properties: AustraliaBoundaryProperties & {
      readonly fill_color: string;
      readonly has_data: boolean;
      readonly metric_value: number | null;
      readonly normalized: number | null;
      readonly region_slug: string | null;
      readonly tone: RegionHeatRow["tone"];
    };
  })[];
}

const boundaries = australiaStateBoundaries as unknown as AustraliaBoundaryCollection;

export function buildAustraliaRegionGeoJson(
  rows: readonly RegionHeatRow[],
): AustraliaRegionFeatureCollection {
  const rowByState = new Map(
    rows
      .filter((row): row is RegionHeatRow & { readonly stateCode: string } => row.stateCode !== null)
      .map((row) => [row.stateCode, row] as const),
  );

  return {
    ...boundaries,
    features: boundaries.features.map((feature) => {
      const row = rowByState.get(feature.properties.state_code_2021);
      const hasData = row?.metricValue !== null && row?.metricValue !== undefined;
      const tone = hasData ? row.tone : "withheld";

      return {
        ...feature,
        properties: {
          ...feature.properties,
          fill_color: hasData ? regionHeatColour(row.normalized) : REGION_TONE_COLOURS.withheld,
          has_data: hasData,
          metric_value: hasData ? row.metricValue : null,
          normalized: hasData ? row.normalized : null,
          region_slug: hasData ? row.region.slug : null,
          tone,
        },
      };
    }),
  };
}
