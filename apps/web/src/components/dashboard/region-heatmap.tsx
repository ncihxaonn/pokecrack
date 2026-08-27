"use client";

import React, { useMemo, useState } from "react";
import type { Route } from "next";
import Link from "next/link";

import type { RegionMetric } from "@/data/types";
import { formatCompactNumber, formatProbability } from "@/lib/format";
import styles from "./region-heatmap.module.css";

export type RegionHeatMetric = "rate" | "packs";

type MapCoordinate = Readonly<{ x: number; y: number }>;
type GeoCoordinate = Readonly<{ lat: number; lng: number }>;

export interface RegionHeatRow {
  readonly coordinate: MapCoordinate | null;
  readonly metricValue: number | null;
  readonly normalized: number | null;
  readonly region: RegionMetric;
  readonly tone: "cool" | "mid" | "hot" | "withheld";
}

const regionAnchors: Readonly<Record<string, GeoCoordinate>> = {
  "au-wa-perth": { lat: -31.9523, lng: 115.8613 },
  "au-vic-melbourne": { lat: -37.8136, lng: 144.9631 },
  "au-nsw-sydney": { lat: -33.8688, lng: 151.2093 },
  "au-qld-brisbane": { lat: -27.4698, lng: 153.0251 },
};

// These dimensions and bounds match scripts/generate-world-map.mjs output.
const worldMap = {
  width: 190,
  height: 72,
  lat: { min: -56, max: 71 },
  lng: { min: -168, max: 168 },
} as const;

function projectMapCoordinate(coordinate: GeoCoordinate): MapCoordinate {
  return {
    x: worldMap.width * (coordinate.lng - worldMap.lng.min) / (worldMap.lng.max - worldMap.lng.min),
    y: worldMap.height * (worldMap.lat.max - coordinate.lat) / (worldMap.lat.max - worldMap.lat.min),
  };
}

const metricOptions: readonly { value: RegionHeatMetric; label: string }[] = [
  { value: "rate", label: "Observed rate" },
  { value: "packs", label: "Sample volume" },
];

function metricValue(region: RegionMetric, metric: RegionHeatMetric): number | null {
  const value = metric === "rate" ? region.hitRate : region.packsObserved;
  return typeof value === "number" && Number.isFinite(value) ? value : null;
}

function heatTone(normalized: number | null): RegionHeatRow["tone"] {
  if (normalized === null) return "withheld";
  if (normalized >= 0.67) return "hot";
  if (normalized >= 0.34) return "mid";
  return "cool";
}

export function buildRegionHeatRows(
  regions: readonly RegionMetric[],
  metric: RegionHeatMetric,
): readonly RegionHeatRow[] {
  const values = regions
    .map((region) => metricValue(region, metric))
    .filter((value): value is number => value !== null);
  const minimum = values.length > 0 ? Math.min(...values) : null;
  const maximum = values.length > 0 ? Math.max(...values) : null;

  return regions
    .map((region) => {
      const value = metricValue(region, metric);
      const anchor = regionAnchors[region.slug];
      const normalized = value === null || minimum === null || maximum === null
        ? null
        : maximum === minimum
          ? 0.5
          : Math.min(1, Math.max(0, (value - minimum) / (maximum - minimum)));
      return {
        coordinate: anchor ? projectMapCoordinate(anchor) : null,
        metricValue: value,
        normalized,
        region,
        tone: heatTone(normalized),
      } satisfies RegionHeatRow;
    })
    .sort((left, right) => {
      if (left.metricValue === null && right.metricValue !== null) return 1;
      if (left.metricValue !== null && right.metricValue === null) return -1;
      if (left.metricValue !== right.metricValue) return (right.metricValue ?? 0) - (left.metricValue ?? 0);
      if (left.region.packsObserved !== right.region.packsObserved) return right.region.packsObserved - left.region.packsObserved;
      return left.region.name.localeCompare(right.region.name);
    });
}

function shortRegionName(region: RegionMetric): string {
  return region.name.replace("Australia · ", "");
}

function displayMetric(row: RegionHeatRow, metric: RegionHeatMetric): string {
  if (row.metricValue === null) return "Withheld";
  return metric === "rate" ? formatProbability(row.metricValue) : `${formatCompactNumber(row.metricValue)} packs`;
}

function legendValues(rows: readonly RegionHeatRow[], metric: RegionHeatMetric): readonly [string, string, string] | null {
  const values = rows
    .map((row) => row.metricValue)
    .filter((value): value is number => value !== null)
    .sort((left, right) => left - right);
  if (values.length === 0) return null;
  const minimum = values[0]!;
  const maximum = values[values.length - 1]!;
  const middle = minimum + (maximum - minimum) / 2;
  const format = metric === "rate" ? formatProbability : (value: number) => formatCompactNumber(value);
  return [format(minimum), format(middle), format(maximum)];
}

export function RegionHeatmap({ regions }: { regions: readonly RegionMetric[] }) {
  const [metric, setMetric] = useState<RegionHeatMetric>("rate");
  const rows = useMemo(() => buildRegionHeatRows(regions, metric), [metric, regions]);
  const ticks = legendValues(rows, metric);
  const plotted = rows.filter((row) => row.coordinate !== null);
  const plottedByHeat = [...plotted].sort((left, right) => (left.normalized ?? -1) - (right.normalized ?? -1));
  const unmappedCount = rows.length - plotted.length;
  const selectedMetricLabel = metric === "rate" ? "Observed rate" : "Sample volume";

  return (
    <section className={styles.atlas} aria-labelledby="coverage-title">
      <header className={styles.header}>
        <div>
          <span className={styles.kicker}>World context · current coverage AU</span>
          <h2 id="coverage-title">Observed regional pull map</h2>
          <p>Compare published regions in this snapshot. Colour shows the relative selected metric; marker size shows sample volume.</p>
        </div>
        <div className={styles.toggle} role="group" aria-label="Heat map metric">
          {metricOptions.map((option) => (
            <button
              type="button"
              key={option.value}
              aria-pressed={metric === option.value}
              onClick={() => setMetric(option.value)}
            >
              {option.label}
            </button>
          ))}
        </div>
      </header>

      <div className={styles.body}>
        <figure className={styles.mapFigure}>
          <span className={styles.coverageBadge}>AU-only published sample</span>
          <svg className={styles.map} viewBox={`0 0 ${worldMap.width} ${worldMap.height}`} role="img" aria-labelledby="region-map-title region-map-description" aria-describedby="coverage-caveat">
            <title id="region-map-title">World map with published Australian regional observations</title>
            <desc id="region-map-description">An accurate dotted world map provides geographic context. Only Australia has published observations. Coloured heat blooms are regional aggregation anchors, not precise observation locations. Exact values and coverage descriptions are listed beside the map. There are no routes or connections between regions.</desc>
            <defs>
              <filter id="regional-heat-blur" x="-80%" y="-80%" width="260%" height="260%">
                <feGaussianBlur stdDeviation="1.15" />
              </filter>
            </defs>
            <image
              data-testid="dotted-world-map"
              href="/world-map-dots.svg"
              width={worldMap.width}
              height={worldMap.height}
              preserveAspectRatio="xMidYMid meet"
              aria-hidden="true"
            />
            <g aria-hidden="true">
              {plottedByHeat.map((row) => {
                const coordinate = row.coordinate as MapCoordinate;
                const radius = 1.15 + Math.min(0.65, Math.sqrt(row.region.packsObserved) / 60);
                return (
                  <g className={`${styles.marker} ${styles[row.tone]}`} key={row.region.slug} transform={`translate(${coordinate.x} ${coordinate.y})`}>
                    <circle className={styles.markerBloom} r={radius * 3.5} filter="url(#regional-heat-blur)" />
                    <circle className={styles.markerHalo} r={radius * 1.9} />
                    <circle className={styles.markerRing} r={radius} />
                    <circle className={styles.markerCore} r="0.48" />
                  </g>
                );
              })}
            </g>
          </svg>

          <figcaption className={styles.caption}>
            {ticks ? (
              <div className={styles.legend} role="img" aria-label={`${selectedMetricLabel}, relative scale within this snapshot: low ${ticks[0]}, midpoint ${ticks[1]}, high ${ticks[2]}`}>
                <span className={styles.legendScale} aria-hidden="true" />
                <span className={styles.legendTicks} aria-hidden="true"><span>{ticks[0]}</span><span>{ticks[1]}</span><span>{ticks[2]}</span></span>
              </div>
            ) : <span className={styles.noValues}>No published values</span>}
            <p id="coverage-caveat">Current published coverage is Australia-only. Colours are relative within this snapshot and do not indicate statistical significance. Higher observed results do not predict future packs, stores, products or individual outcomes.{unmappedCount > 0 ? ` ${unmappedCount} region ${unmappedCount === 1 ? "is" : "are"} listed without a map anchor.` : ""}</p>
          </figcaption>
        </figure>

        <aside className={styles.rail} aria-label="Published regional observations">
          <div className={styles.railHeading}>
            <div><span>Regional view</span><strong>{rows.length}</strong></div>
            <small>{plotted.length}/{rows.length} mapped</small>
          </div>
          <p className="sr-only" role="status" aria-live="polite">{selectedMetricLabel} selected; regional ranking updated.</p>
          {rows.length === 0 ? (
            <p className={styles.empty}>No region aggregates are published in this snapshot.</p>
          ) : (
            <ol className={styles.regionList}>
              {rows.map((row, index) => (
                <li key={row.region.slug}>
                  <Link
                    href={`/regions/${row.region.slug}` as Route}
                    aria-label={`${shortRegionName(row.region)}: ${displayMetric(row, metric)}; coverage: ${row.region.coverage}; ${formatCompactNumber(row.region.packsObserved)} observed packs; ${row.region.independentSources} independent ${row.region.independentSources === 1 ? "source" : "sources"}`}
                  >
                    <span className={`${styles.swatch} ${styles[row.tone]}`} aria-hidden="true" />
                    <span className={styles.rank}>{String(index + 1).padStart(2, "0")}</span>
                    <span className={styles.regionName}><strong>{shortRegionName(row.region)}</strong><small>{row.region.coverage}</small><small>{formatCompactNumber(row.region.packsObserved)} packs · {row.region.independentSources} {row.region.independentSources === 1 ? "source" : "sources"}</small></span>
                    <span className={styles.value}>{displayMetric(row, metric)}</span>
                  </Link>
                </li>
              ))}
            </ol>
          )}
          <Link className={styles.allRegions} href="/regions">Explore all regions <span aria-hidden="true">→</span></Link>
        </aside>
      </div>
    </section>
  );
}
