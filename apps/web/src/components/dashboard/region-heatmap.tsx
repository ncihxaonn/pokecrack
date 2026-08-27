"use client";

import React, { useMemo, useState } from "react";
import type { Route } from "next";
import Link from "next/link";

import type { RegionMetric } from "@/data/types";
import { formatCompactNumber, formatProbability } from "@/lib/format";
import styles from "./region-heatmap.module.css";

export type RegionHeatMetric = "rate" | "packs";

type MapCoordinate = Readonly<{ x: number; y: number }>;

export interface RegionHeatRow {
  readonly coordinate: MapCoordinate | null;
  readonly metricValue: number | null;
  readonly normalized: number | null;
  readonly region: RegionMetric;
  readonly tone: "cool" | "mid" | "hot" | "withheld";
}

const regionAnchors: Readonly<Record<string, MapCoordinate>> = {
  "au-wa-perth": { x: 719, y: 339 },
  "au-vic-melbourne": { x: 787, y: 360 },
  "au-nsw-sydney": { x: 807, y: 342 },
  "au-qld-brisbane": { x: 812, y: 316 },
};

const worldLandPaths = [
  "M72 104C98 70 142 61 173 74c19 8 31 6 51 2l42 13 19 26-12 23-28 8-18 31-27 17-25 7-31-24-45-15-42-32-15-28 3-25Z",
  "M268 205c26 7 48 28 52 53l-10 38-18 42-17 43-15-8-4-37-18-31-7-42 17-35 20-23Z",
  "M366 91l31-21 39 7 17 20-19 17-31-2-19 13-20-12 2-22Z",
  "M405 132c28-22 64-30 97-22l38-15 47 3 32 20 38-3 52 21 61 13 41 30-18 18-36-5-23 19-31-7-36 19-47-4-28 23-41-14-40-34-38-11-33 14-34-10-32-31-25-17 1-26Z",
  "M438 196c24-13 55-9 74 7l18 35-10 46-31 48-31-3-19-38-16-47 15-48Z",
  "M704 300l33-18 46 7 32 24-8 31-38 20-43-7-25-27 3-30Z",
  "M831 341l11 6 7 21-9 19-8-7 3-20-4-19Z",
  "M750 213l9-13 8 14-8 18-9-19Z",
];
const australiaLandPath = worldLandPaths[5]!;

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
      const normalized = value === null || minimum === null || maximum === null
        ? null
        : maximum === minimum
          ? 0.5
          : Math.min(1, Math.max(0, (value - minimum) / (maximum - minimum)));
      return {
        coordinate: regionAnchors[region.slug] ?? null,
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
          <svg className={styles.map} viewBox="0 0 900 430" role="img" aria-labelledby="region-map-title region-map-description" aria-describedby="coverage-caveat">
            <title id="region-map-title">World map with published Australian regional observations</title>
            <desc id="region-map-description">Only Australia has published observations. Coloured circles are regional aggregation anchors, not precise observation locations. Exact values and coverage descriptions are listed beside the map.</desc>
            <defs>
              <pattern id="world-dot-pattern" width="9" height="9" patternUnits="userSpaceOnUse">
                <circle className={styles.worldDot} cx="2.2" cy="2.2" r="1.35" />
              </pattern>
              <pattern id="world-grid-pattern" width="36" height="36" patternUnits="userSpaceOnUse">
                <path d="M36 0H0V36" fill="none" />
              </pattern>
            </defs>
            <rect className={styles.grid} width="900" height="430" fill="url(#world-grid-pattern)" />
            <g className={styles.land} aria-hidden="true">
              {worldLandPaths.map((path) => <path d={path} key={path} fill="url(#world-dot-pattern)" />)}
            </g>
            <path className={styles.australiaOutline} aria-hidden="true" d={australiaLandPath} />
            <g aria-hidden="true">
              {plotted.map((row) => {
                const coordinate = row.coordinate as MapCoordinate;
                const radius = 11 + Math.min(11, Math.sqrt(row.region.packsObserved) / 3.5);
                return (
                  <g className={`${styles.marker} ${styles[row.tone]}`} key={row.region.slug} transform={`translate(${coordinate.x} ${coordinate.y})`}>
                    <circle className={styles.markerHalo} r={radius * 1.85} />
                    <circle className={styles.markerRing} r={radius} />
                    <circle className={styles.markerCore} r="4.5" />
                  </g>
                );
              })}
            </g>
            <g className={styles.mapLabel} aria-hidden="true">
              <path d="M690 382h142" />
              <text x="690" y="402">AUSTRALIA · PUBLISHED SAMPLE</text>
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
