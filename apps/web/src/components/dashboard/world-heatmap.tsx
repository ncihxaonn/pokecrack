"use client";

import React, { useId, useMemo, useState } from "react";

import { defaultWorldHeatMetric, type WorldHeatMetric } from "@/app/_lib/world-map-query";
import mapData from "@/data/world-map-110m.json";
import type { CountryMapCell, ObservationReadiness } from "@/data/types";
import {
  formatDate,
  formatProbability,
  formatSignedProbability,
} from "@/lib/format";
import styles from "./world-heatmap.module.css";

export type { WorldHeatMetric } from "@/app/_lib/world-map-query";

export interface WorldHeatRow {
  readonly cell: CountryMapCell;
  readonly metricValue: number | null;
  readonly fill: string;
  readonly status: "observed" | "published" | "withheld";
}

const integer = new Intl.NumberFormat("en-US");
const metricOptions: readonly { value: WorldHeatMetric; label: string }[] = [
  { value: "coverage", label: "Pack coverage" },
  { value: "delta", label: "Baseline delta" },
  { value: "rate", label: "Observed rate" },
];

function clamp(value: number, minimum: number, maximum: number) {
  return Math.min(maximum, Math.max(minimum, value));
}

function interpolateHex(start: string, end: string, amount: number) {
  const from = [1, 3, 5].map((offset) => Number.parseInt(start.slice(offset, offset + 2), 16));
  const to = [1, 3, 5].map((offset) => Number.parseInt(end.slice(offset, offset + 2), 16));
  return `#${from.map((channel, index) => {
    const mixed = Math.round(channel + ((to[index] ?? channel) - channel) * amount);
    return mixed.toString(16).padStart(2, "0");
  }).join("")}`;
}

export function getWorldMapFill(value: number, metric: WorldHeatMetric): string {
  if (metric === "coverage") {
    const bounded = clamp(value, 0, 1_500);
    if (bounded <= 750) {
      return interpolateHex("#e7f2eb", "#43a475", bounded / 750);
    }
    return interpolateHex("#43a475", "#075f39", (bounded - 750) / 750);
  }

  if (metric === "delta") {
    const bounded = clamp(value, -0.05, 0.05);
    if (bounded <= 0) {
      return interpolateHex("#789388", "#edf2ee", (bounded + 0.05) / 0.05);
    }
    return interpolateHex("#edf2ee", "#148a54", bounded / 0.05);
  }

  const bounded = clamp(value, 0, 0.3);
  if (bounded <= 0.15) {
    return interpolateHex("#e7f2eb", "#43a475", bounded / 0.15);
  }
  return interpolateHex("#43a475", "#075f39", (bounded - 0.15) / 0.15);
}

export function buildWorldHeatRows(
  cells: readonly CountryMapCell[],
  metric: WorldHeatMetric,
): readonly WorldHeatRow[] {
  return [...cells]
    .sort((left, right) => left.countryName.localeCompare(right.countryName))
    .map((cell) => {
      const metricValue = metric === "coverage"
        ? cell.packsObserved
        : metric === "delta"
          ? cell.deltaFromBaseline
          : cell.hitRate;
      const status = metric === "coverage"
        ? "observed"
        : metricValue === null
          ? "withheld"
          : "published";
      return {
        cell,
        metricValue,
        fill: metricValue === null ? "withheld" : getWorldMapFill(metricValue, metric),
        status,
      } satisfies WorldHeatRow;
    });
}

function stateLabel(cell: CountryMapCell) {
  if (cell.state === "insufficient") return "Withheld";
  if (cell.state === "pending") return "Publication pending";
  if (cell.state === "anomaly") return "Possible anomaly";
  if (cell.state === "watch") return "Watch";
  return "Published";
}

export function WorldHeatmap({
  cells,
  coverageSummary,
  observations,
  initialMetric,
}: {
  readonly cells: readonly CountryMapCell[];
  readonly coverageSummary: string;
  readonly observations: ObservationReadiness;
  readonly initialMetric?: WorldHeatMetric;
}) {
  const [metric, setMetric] = useState<WorldHeatMetric>(
    initialMetric ?? defaultWorldHeatMetric(observations.countriesWithPublishedRate),
  );
  const rows = useMemo(() => buildWorldHeatRows(cells, metric), [cells, metric]);
  const cellsByCountry = useMemo(
    () => new Map(rows.map((row) => [row.cell.countryCode, row])),
    [rows],
  );
  const instanceId = useId().replaceAll(":", "");
  const withheldPatternId = `world-withheld-${instanceId}`;
  const publishedRateCount = cells.filter((cell) => cell.hitRate !== null).length;
  const withheldCount = rows.length - publishedRateCount;
  const pendingCount = rows.filter((row) => row.cell.state === "pending").length;
  const metricLabel = metric === "coverage"
    ? "Observed pack coverage"
    : metric === "delta"
      ? "Baseline delta"
      : "Observed rate";
  const period = observations.period
    ? `${formatDate(observations.period.start)} - ${formatDate(observations.period.end)}`
    : "No verified period yet";
  const readinessLabel = observations.status === "empty"
    ? "Awaiting observations"
    : observations.status === "collecting"
      ? "Collection in progress"
      : "Published";
  const mapDescription = rows.length === 0
    ? "No verified country-level pack-opening observations are published. Every country is shown in the neutral no-data colour."
    : metric === "coverage"
      ? `${rows.length} countries have verified pack-opening observations. Colour shows fixed-scale sample volume only, not a hit rate or representative demand.`
      : `${rows.length} countries have verified observations: ${publishedRateCount} publish a rate, ${pendingCount} await reviewed publication, and ${withheldCount - pendingCount} remain below the evidence threshold.`;

  const selectMetric = (nextMetric: WorldHeatMetric) => {
    setMetric(nextMetric);
    const url = new URL(window.location.href);
    url.searchParams.set("metric", nextMetric);
    window.history.replaceState(null, "", `${url.pathname}${url.search}${url.hash}`);
  };

  const countryFill = (countryCode: string | null) => {
    if (!countryCode) return "#dfe7e1";
    const row = cellsByCountry.get(countryCode);
    if (!row) return "#dfe7e1";
    return row.status === "withheld" ? `url(#${withheldPatternId})` : row.fill;
  };

  return (
    <section className={styles.atlas} aria-labelledby="world-coverage-title">
      <header className={styles.header}>
        <div>
          <span className={styles.kicker}>Global evidence map</span>
          <h2 id="world-coverage-title">
            {metric === "coverage" ? "Worldwide evidence coverage" : "Worldwide qualifying-hit map"}
          </h2>
          <p>
            {metric === "coverage"
              ? "Verified pack-opening sample volume by country. This coverage view is not a hit-rate comparison."
              : "Country-level qualifying-hit rates from verified pack-opening samples. Catalog records and discovery activity never enter the denominator."}
          </p>
        </div>
        <div className={styles.toggle} role="group" aria-label="World heat map metric">
          {metricOptions.map((option) => (
            <button
              type="button"
              key={option.value}
              aria-pressed={metric === option.value}
              onClick={() => selectMetric(option.value)}
            >
              {option.label}
            </button>
          ))}
        </div>
      </header>

      <div className={styles.body}>
        <figure className={styles.mapFigure}>
          <div className={styles.mapStage}>
            <svg
              className={styles.map}
              viewBox={mapData.viewBox}
              preserveAspectRatio="xMidYMid meet"
              role="img"
              aria-labelledby={`world-map-title-${instanceId}`}
              aria-describedby={`world-map-description-${instanceId} world-map-caveat-${instanceId}`}
              focusable="false"
            >
              <title id={`world-map-title-${instanceId}`}>{`${metricLabel} across the world`}</title>
              <desc id={`world-map-description-${instanceId}`}>{mapDescription}</desc>
              <defs>
                <pattern
                  id={withheldPatternId}
                  width="7"
                  height="7"
                  patternUnits="userSpaceOnUse"
                  patternTransform="rotate(35)"
                >
                  <rect width="7" height="7" fill="#dbe4dd" />
                  <path d="M0 0V7" stroke="#88978e" strokeWidth="2" />
                </pattern>
              </defs>
              <g aria-hidden="true">
                {mapData.countries.map((country, index) => (
                  <path
                    className={styles.country}
                    d={country.path}
                    fill={countryFill(country.countryCode)}
                    key={`${country.countryName}-${index}`}
                  />
                ))}
                {mapData.tinyCountries.map((country, index) => {
                  const row = country.countryCode
                    ? cellsByCountry.get(country.countryCode)
                    : undefined;
                  const fill = row?.status === "withheld"
                      ? `url(#${withheldPatternId})`
                      : row
                        ? row.fill
                        : "#dfe7e1";
                  return (
                    <circle
                      className={styles.tinyCountry}
                      cx={country.x}
                      cy={country.y}
                      fill={fill}
                      key={`${country.countryName}-${index}`}
                      r={row ? 2.8 : 1.8}
                    />
                  );
                })}
              </g>
            </svg>
            {(metric === "coverage" ? rows.length === 0 : publishedRateCount === 0) ? (
              <div className={styles.emptyMapMessage} role="note">
                <strong>{metric === "coverage"
                  ? "No verified pack coverage yet"
                  : "No country-level rates published yet"}</strong>
                <span>{rows.length === 0
                  ? "The map stays neutral until verified samples meet the publication threshold."
                  : pendingCount > 0
                    ? `${rows.length} ${rows.length === 1 ? "country is" : "countries are"} observed; ${pendingCount} ${pendingCount === 1 ? "has" : "have"} met the evidence threshold and await reviewed publication.`
                    : `${rows.length} ${rows.length === 1 ? "country is" : "countries are"} observed; all remain below the publication threshold.`}</span>
              </div>
            ) : null}
          </div>

          <figcaption className={styles.caption}>
            <div className={styles.legend}>
              <span
                className={`${styles.legendScale} ${metric === "coverage" ? styles.coverageScale : metric === "delta" ? styles.deltaScale : styles.rateScale}`}
                aria-hidden="true"
              />
              <span className={styles.legendTicks} aria-hidden="true">
                {metric === "coverage" ? (
                  <><span>0 packs</span><span>750</span><span>≥ 1,500</span></>
                ) : metric === "delta" ? (
                  <><span>≤ −5 pp</span><span>0 pp</span><span>≥ +5 pp</span></>
                ) : (
                  <><span>0%</span><span>15%</span><span>≥ 30%</span></>
                )}
              </span>
              <span className={styles.legendKeys}>
                <span className={styles.noDataKey}><i aria-hidden="true" />Not observed</span>
                {metric === "coverage" ? (
                  <span className={styles.observedKey}><i aria-hidden="true" />Observed pack sample</span>
                ) : (
                  <>
                    <span className={styles.withheldKey}><i aria-hidden="true" />Observed, rate withheld</span>
                    <span className={styles.publishedKey}><i aria-hidden="true" />Published rate</span>
                  </>
                )}
              </span>
            </div>
            <p id={`world-map-caveat-${instanceId}`}>
              {metric === "coverage"
                ? "Fixed absolute 0–1,500 pack colour scale; this shows sample volume, not a hit rate or representative demand. Unobserved countries remain neutral."
                : "Fixed absolute colour scale; values are never rescaled to the current snapshot. Higher historical observations do not predict future packs, products, stores or countries."}
            </p>
          </figcaption>
        </figure>

        <aside className={styles.rail} aria-label="Global observation readiness">
          <div className={styles.railIntro}>
            <span>Observation readiness</span>
            <strong>{readinessLabel}</strong>
            <small>{period}</small>
          </div>
          <dl className={styles.readinessList}>
            <div><dt>Countries observed</dt><dd>{integer.format(observations.countriesObserved)}</dd></div>
            <div><dt>Published rates</dt><dd>{integer.format(observations.countriesWithPublishedRate)}</dd></div>
            <div><dt>Observed packs</dt><dd>{integer.format(observations.observedPacks)}</dd></div>
            <div><dt>Complete openings</dt><dd>{integer.format(observations.completeOpenings)}</dd></div>
          </dl>
          <p className={styles.coverageSummary}>{coverageSummary}</p>
          <p className={styles.sourceNote}>{observations.sourceCountryContributions === 0
            ? "No verified source-country contributions have reached publication yet."
            : `${integer.format(observations.sourceCountryContributions)} source-country contributions. A source may appear in more than one country, so this is not a global independent-source count.`}
          </p>
          <p className="sr-only" role="status" aria-live="polite">
            {metricLabel} selected. The world map has updated.
          </p>
        </aside>
      </div>

      <div className={styles.tableBlock}>
        <div className={styles.tableHeading}>
          <strong>Country observations</strong>
          <small>Alphabetical, not a ranking</small>
        </div>
        <div className={styles.tableFrame} role="region" aria-label="Exact global country values" tabIndex={0}>
          <table>
            <caption className="sr-only">Exact country-level values for {period}</caption>
            <thead>
              <tr><th scope="col">Country</th><th scope="col">Packs</th><th scope="col">Sources</th><th scope="col">Observed</th><th scope="col">Baseline</th><th scope="col">Delta</th><th scope="col">Status</th></tr>
            </thead>
            <tbody>
              {rows.length === 0 ? (
                <tr><td colSpan={7} className={styles.empty}>No verified country observations are published yet.</td></tr>
              ) : rows.map((row) => (
                <tr key={row.cell.countryCode}>
                  <td data-label="Country"><strong>{row.cell.countryName}</strong><small>{row.cell.countryCode}</small></td>
                  <td data-label="Packs">{integer.format(row.cell.packsObserved)}</td>
                  <td data-label="Sources">{integer.format(row.cell.independentSources)}</td>
                  <td data-label="Observed">{formatProbability(row.cell.hitRate)}</td>
                  <td data-label="Baseline">{formatProbability(row.cell.baselineRate)}</td>
                  <td data-label="Delta">{formatSignedProbability(row.cell.deltaFromBaseline)}</td>
                  <td data-label="Status"><span className={`${styles.status} ${styles[`status${row.cell.state}`]}`}>{stateLabel(row.cell)}</span></td>
                </tr>
              ))}
            </tbody>
          </table>
        </div>
      </div>
    </section>
  );
}
