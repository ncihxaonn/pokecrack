"use client";

import React, { useMemo, useState } from "react";
import type { Route } from "next";
import Link from "next/link";

import type { RegionMetric } from "@/data/types";
import { formatCompactNumber, formatProbability } from "@/lib/format";
import { RegionalMap } from "./regional-map";
import styles from "./region-heatmap.module.css";

export type RegionHeatMetric = "rate" | "packs";

type GeoCoordinate = Readonly<{ lat: number; lng: number }>;

export interface RegionHeatRow {
  readonly coordinate: GeoCoordinate | null;
  readonly metricValue: number | null;
  readonly normalized: number | null;
  readonly region: RegionMetric;
  readonly stateAbbreviation: string | null;
  readonly stateCode: string | null;
  readonly tone: "cool" | "mid" | "hot" | "withheld";
}

const regionMapMetadata: Readonly<Record<string, Readonly<{
  abbreviation: string;
  coordinate: GeoCoordinate;
  stateCode: string;
}>>> = {
  "au-wa-perth": { abbreviation: "WA", coordinate: { lat: -25, lng: 121 }, stateCode: "5" },
  "au-vic-melbourne": { abbreviation: "VIC", coordinate: { lat: -37.25, lng: 143.4 }, stateCode: "2" },
  "au-nsw-sydney": { abbreviation: "NSW", coordinate: { lat: -31.5, lng: 146.2 }, stateCode: "1" },
  "au-qld-brisbane": { abbreviation: "QLD", coordinate: { lat: -22, lng: 143 }, stateCode: "3" },
};

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
      const mapMetadata = regionMapMetadata[region.slug];
      const normalized = value === null || minimum === null || maximum === null
        ? null
        : maximum === minimum
          ? 0.5
          : Math.min(1, Math.max(0, (value - minimum) / (maximum - minimum)));
      return {
        coordinate: mapMetadata?.coordinate ?? null,
        metricValue: value,
        normalized,
        region,
        stateAbbreviation: mapMetadata?.abbreviation ?? null,
        stateCode: mapMetadata?.stateCode ?? null,
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
    <section className={`${styles.atlas} dashboard-feature`} aria-labelledby="coverage-title">
      <header className={styles.header}>
        <div>
          <span className={styles.kicker}>Australia · state-level published coverage</span>
          <h2 id="coverage-title">Observed regional pull map</h2>
          <p>Compare published regions in this snapshot. State fill shows the relative selected metric; labels show exact aggregate values.</p>
        </div>
        <div className={styles.toggle} role="group" aria-label="Heat map metric" data-selected={metric}>
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
          <RegionalMap rows={rows} metric={metric} metricLabel={selectedMetricLabel} />

          <figcaption className={styles.caption}>
            {ticks ? (
              <div key={metric} className={styles.legend} role="img" aria-label={`${selectedMetricLabel}, relative scale within this snapshot: low ${ticks[0]}, midpoint ${ticks[1]}, high ${ticks[2]}`}>
                <span className={styles.legendScale} aria-hidden="true" />
                <span className={styles.legendTicks} aria-hidden="true"><span>{ticks[0]}</span><span>{ticks[1]}</span><span>{ticks[2]}</span></span>
              </div>
            ) : <span className={styles.noValues}>No published values</span>}
            <p id="coverage-caveat">Current published coverage is Australia-only. Uncoloured states have no published value. Colours are relative within this snapshot and do not indicate statistical significance. Boundaries are simplified from <a href="https://www.abs.gov.au/statistics/standards/australian-statistical-geography-standard-asgs/edition-3-july-2021-june-2026/access-and-downloads/digital-boundary-files" target="_blank" rel="noreferrer">ABS ASGS 2021</a> principal landmasses for cartographic display, not legal definition. Higher observed results do not predict future outcomes.{unmappedCount > 0 ? ` ${unmappedCount} region ${unmappedCount === 1 ? "is" : "are"} listed without a map anchor.` : ""}</p>
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
            <ol key={metric} className={styles.regionList}>
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
