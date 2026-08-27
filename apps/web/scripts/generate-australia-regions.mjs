import { writeFileSync } from "node:fs";
import { resolve } from "node:path";

const sourceEndpoint = "https://geo.abs.gov.au/arcgis/rest/services/ASGS2021/STE/MapServer/1/query";
const sourcePage = "https://www.abs.gov.au/statistics/standards/australian-statistical-geography-standard-asgs/edition-3-july-2021-june-2026/access-and-downloads/digital-boundary-files";
const expectedStateCodes = ["1", "2", "3", "4", "5", "6", "7", "8"];

const query = new URLSearchParams({
  where: `state_code_2021 IN (${expectedStateCodes.map((code) => `'${code}'`).join(",")})`,
  outFields: "state_code_2021,state_name_2021",
  returnGeometry: "true",
  outSR: "4326",
  maxAllowableOffset: "0.05",
  geometryPrecision: "3",
  f: "geojson",
});

function ringArea(ring) {
  let area = 0;
  for (let index = 0; index < ring.length - 1; index += 1) {
    const current = ring[index];
    const next = ring[index + 1];
    area += current[0] * next[1] - next[0] * current[1];
  }
  return Math.abs(area / 2);
}

function principalRing(geometry) {
  const rings = geometry.type === "Polygon"
    ? geometry.coordinates
    : geometry.type === "MultiPolygon"
      ? geometry.coordinates.flat()
      : [];

  const ring = rings.reduce((largest, candidate) => (
    ringArea(candidate) > ringArea(largest) ? candidate : largest
  ), []);

  if (ring.length < 4) {
    throw new Error(`Could not find a valid principal landmass in ${geometry.type}.`);
  }

  return ring;
}

const response = await fetch(`${sourceEndpoint}?${query.toString()}`);
if (!response.ok) {
  throw new Error(`ABS boundary request failed with ${response.status} ${response.statusText}.`);
}

const source = await response.json();
if (source.type !== "FeatureCollection" || !Array.isArray(source.features)) {
  throw new Error("ABS boundary response was not a GeoJSON FeatureCollection.");
}

const features = source.features
  .map((feature) => {
    const stateCode = feature.properties?.state_code_2021;
    const stateName = feature.properties?.state_name_2021;
    if (!expectedStateCodes.includes(stateCode) || typeof stateName !== "string" || !feature.geometry) {
      throw new Error("ABS boundary response contained an unexpected feature.");
    }

    return {
      type: "Feature",
      id: stateCode,
      properties: {
        state_code_2021: stateCode,
        state_name_2021: stateName,
      },
      geometry: {
        type: "Polygon",
        coordinates: [principalRing(feature.geometry)],
      },
    };
  })
  .sort((left, right) => Number(left.id) - Number(right.id));

const receivedCodes = features.map((feature) => feature.id);
if (receivedCodes.length !== expectedStateCodes.length || receivedCodes.some((code, index) => code !== expectedStateCodes[index])) {
  throw new Error(`Expected ABS state codes ${expectedStateCodes.join(", ")}; received ${receivedCodes.join(", ")}.`);
}

const output = {
  type: "FeatureCollection",
  name: "Australia state and territory principal landmasses",
  source: sourcePage,
  note: "Simplified ABS ASGS 2021 cartographic boundaries. Principal landmass only; not a legal boundary definition.",
  features,
};

writeFileSync(
  resolve(import.meta.dirname, "../src/data/australia-state-boundaries.json"),
  `${JSON.stringify(output, null, 2)}\n`,
);
