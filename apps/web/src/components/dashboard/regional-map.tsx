"use client";

import { useEffect, useMemo, useRef, useState } from "react";
import type { GeoJSONSource, Map as MapLibreMap, Marker as MapLibreMarker } from "maplibre-gl";
import "maplibre-gl/dist/maplibre-gl.css";

import { formatCompactNumber, formatProbability } from "@/lib/format";
import type { RegionHeatMetric, RegionHeatRow } from "./region-heatmap";
import { buildAustraliaRegionGeoJson, regionHeatColour } from "./regional-map-data";
import styles from "./regional-map.module.css";

const SOURCE_ID = "australia-regions";
const OUTLINE_LAYER_ID = "australia-region-outline";
const BORDER_LAYER_ID = "australia-region-border";
const FILL_LAYER_ID = "australia-region-fill";

type MapLibreModule = typeof import("maplibre-gl");
type GeoJsonData = Parameters<GeoJSONSource["setData"]>[0];

function createBlankStyle() {
  return {
    version: 8 as const,
    name: "PokeCrack blank regional canvas",
    sources: {},
    layers: [
      {
        id: "regional-canvas",
        type: "background" as const,
        paint: { "background-color": "#eef2f6" },
      },
    ],
  };
}

function markerValue(row: RegionHeatRow, metric: RegionHeatMetric): string {
  if (row.metricValue === null) return "Withheld";
  return metric === "rate" ? formatProbability(row.metricValue) : formatCompactNumber(row.metricValue);
}

function replaceMarkers(
  maplibre: MapLibreModule,
  map: MapLibreMap,
  currentMarkers: MapLibreMarker[],
  rows: readonly RegionHeatRow[],
  metric: RegionHeatMetric,
) {
  currentMarkers.forEach((marker) => marker.remove());
  currentMarkers.length = 0;

  rows.forEach((row) => {
    if (!row.coordinate || !row.stateAbbreviation || row.metricValue === null) return;

    const element = document.createElement("div");
    element.className = styles.markerLabel ?? "";
    element.style.setProperty("--marker-tone", regionHeatColour(row.normalized));
    element.setAttribute("aria-hidden", "true");

    const abbreviation = document.createElement("strong");
    abbreviation.textContent = row.stateAbbreviation;
    const value = document.createElement("span");
    value.textContent = markerValue(row, metric);
    element.append(abbreviation, value);

    const marker = new maplibre.Marker({ anchor: "center", element })
      .setLngLat([row.coordinate.lng, row.coordinate.lat])
      .addTo(map);
    currentMarkers.push(marker);
  });
}

function syncMap(
  maplibre: MapLibreModule,
  map: MapLibreMap,
  markers: MapLibreMarker[],
  geoJson: ReturnType<typeof buildAustraliaRegionGeoJson>,
  rows: readonly RegionHeatRow[],
  metric: RegionHeatMetric,
) {
  const source = map.getSource(SOURCE_ID) as GeoJSONSource | undefined;
  source?.setData(geoJson as unknown as GeoJsonData);
  replaceMarkers(maplibre, map, markers, rows, metric);
}

export function RegionalMap({
  rows,
  metric,
  metricLabel,
}: Readonly<{
  rows: readonly RegionHeatRow[];
  metric: RegionHeatMetric;
  metricLabel: string;
}>) {
  const containerRef = useRef<HTMLDivElement>(null);
  const mapRef = useRef<MapLibreMap | null>(null);
  const maplibreRef = useRef<MapLibreModule | null>(null);
  const markersRef = useRef<MapLibreMarker[]>([]);
  const [status, setStatus] = useState<"loading" | "ready" | "error">("loading");
  const geoJson = useMemo(() => buildAustraliaRegionGeoJson(rows), [rows]);
  const latestRef = useRef({ geoJson, metric, rows });
  const mappedCount = rows.filter((row) => row.stateCode !== null && row.metricValue !== null).length;

  useEffect(() => {
    let active = true;

    async function initialiseMap() {
      try {
        const maplibre = await import("maplibre-gl");
        if (!active || !containerRef.current) return;

        maplibreRef.current = maplibre;
        const map = new maplibre.Map({
          attributionControl: false,
          center: [134, -27],
          container: containerRef.current,
          fadeDuration: 0,
          interactive: false,
          maxZoom: 6,
          minZoom: 2,
          pitch: 0,
          renderWorldCopies: false,
          style: createBlankStyle(),
          zoom: 3,
        });
        mapRef.current = map;

        map.once("load", () => {
          if (!active) return;

          const latest = latestRef.current;
          map.addSource(SOURCE_ID, {
            type: "geojson",
            data: latest.geoJson as unknown as GeoJsonData,
          });
          map.addLayer({
            id: FILL_LAYER_ID,
            type: "fill",
            source: SOURCE_ID,
            paint: {
              "fill-color": ["get", "fill_color"],
              "fill-opacity": ["case", ["get", "has_data"], 0.88, 0.78],
            },
          });
          map.addLayer({
            id: OUTLINE_LAYER_ID,
            type: "line",
            source: SOURCE_ID,
            paint: {
              "line-color": "#aeb8c5",
              "line-opacity": 0.72,
              "line-width": 2.6,
            },
          });
          map.addLayer({
            id: BORDER_LAYER_ID,
            type: "line",
            source: SOURCE_ID,
            paint: {
              "line-color": "#ffffff",
              "line-opacity": 0.96,
              "line-width": 1.25,
            },
          });
          map.fitBounds([[112, -44.5], [154, -9.5]], {
            duration: 0,
            padding: { top: 26, right: 28, bottom: 20, left: 28 },
          });

          const canvas = map.getCanvas();
          canvas.tabIndex = -1;
          canvas.setAttribute("aria-hidden", "true");
          replaceMarkers(maplibre, map, markersRef.current, latest.rows, latest.metric);
          setStatus("ready");
        });
      } catch {
        if (active) setStatus("error");
      }
    }

    void initialiseMap();

    return () => {
      active = false;
      markersRef.current.forEach((marker) => marker.remove());
      markersRef.current = [];
      mapRef.current?.remove();
      mapRef.current = null;
      maplibreRef.current = null;
    };
  }, []);

  useEffect(() => {
    latestRef.current = { geoJson, metric, rows };

    const map = mapRef.current;
    const maplibre = maplibreRef.current;
    if (!map || !maplibre || !map.isStyleLoaded()) return;
    syncMap(maplibre, map, markersRef.current, geoJson, rows, metric);
  }, [geoJson, metric, rows]);

  const mapDescription = `Australia state and territory choropleth for ${metricLabel.toLowerCase()}. ${mappedCount} of 8 states and territories have published values. Exact values are listed beside the map. No routes or connections are shown.`;

  return (
    <div className={styles.shell}>
      <div className={styles.viewport} role="img" aria-label={mapDescription} data-testid="australia-region-map">
        <div ref={containerRef} className={styles.map} aria-hidden="true" />
        <span className={styles.coverageBadge} aria-hidden="true">{mappedCount} of 8 with data</span>
        {status === "loading" ? <span className={styles.loading} aria-hidden="true">Rendering regional map…</span> : null}
      </div>
      {status === "error" ? <p className={styles.error} role="status">Regional map unavailable. Exact values remain available in the regional list.</p> : null}
    </div>
  );
}
