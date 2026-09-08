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
import {
  formatCoverageAttribution,
  sourceNativeLanguageTag,
} from "@/lib/coverage-attribution";
import styles from "./world-heatmap.module.css";

export type { WorldHeatMetric } from "@/app/_lib/world-map-query";

export interface WorldHeatRow {
  readonly cell: CountryMapCell;
  readonly metricValue: number | null;
  readonly fill: string;
  readonly status: "observed" | "published" | "withheld";
}

export interface GlobalFocusCountry {
  readonly countryCode:
    | "JP"
    | "AU"
    | "CN"
    | "RU"
    | "CA"
    | "MX"
    | "BR"
    | "PR"
    | "GT"
    | "PA"
    | "CR"
    | "CO"
    | "EC"
    | "PE"
    | "AR"
    | "CL"
    | "UY"
    | "KR"
    | "TW"
    | "HK"
    | "TH"
    | "ID"
    | "MY"
    | "PH"
    | "VN"
    | "IN";
  readonly countryName: string;
}

export const GLOBAL_FOCUS_COUNTRIES: readonly GlobalFocusCountry[] = [
  { countryCode: "JP", countryName: "Japan" },
  { countryCode: "AU", countryName: "Australia" },
  { countryCode: "CN", countryName: "China" },
  { countryCode: "RU", countryName: "Russia" },
  { countryCode: "CA", countryName: "Canada" },
  { countryCode: "MX", countryName: "Mexico" },
  { countryCode: "BR", countryName: "Brazil" },
  { countryCode: "PR", countryName: "Puerto Rico" },
  { countryCode: "GT", countryName: "Guatemala" },
  { countryCode: "PA", countryName: "Panama" },
  { countryCode: "CR", countryName: "Costa Rica" },
  { countryCode: "CO", countryName: "Colombia" },
  { countryCode: "EC", countryName: "Ecuador" },
  { countryCode: "PE", countryName: "Peru" },
  { countryCode: "AR", countryName: "Argentina" },
  { countryCode: "CL", countryName: "Chile" },
  { countryCode: "UY", countryName: "Uruguay" },
  { countryCode: "KR", countryName: "South Korea" },
  { countryCode: "TW", countryName: "Taiwan" },
  { countryCode: "HK", countryName: "Hong Kong" },
  { countryCode: "TH", countryName: "Thailand" },
  { countryCode: "ID", countryName: "Indonesia" },
  { countryCode: "MY", countryName: "Malaysia" },
  { countryCode: "PH", countryName: "Philippines" },
  { countryCode: "VN", countryName: "Vietnam" },
  { countryCode: "IN", countryName: "India" },
];

export const WORLD_MAP_PALETTE = {
  background: "#ffffff",
  noData: "#e7e7e7",
  boundary: "#808080",
  quantitativeLow: "#2563eb",
  quantitativeMid: "#0f766e",
  quantitativeHigh: "#c2410c",
  deltaLow: "#cc785c",
  deltaMid: "#d9d9d9",
  deltaHigh: "#7f4bf3",
  withheldBase: "#7f4bf3",
  withheldStripe: "#eee7fb",
  focus: "#9b6a12",
  labelAccent: "#702675",
} as const;

// Absolute pack-count bands: do not normalize to the current countries or maximum.
// The legend uses this same definition so a colour always means the same range.
export const WORLD_COVERAGE_BANDS = [
  { minimum: 0, label: "0–24", color: "#2563eb" },
  { minimum: 25, label: "25–49", color: "#0e7490" },
  { minimum: 50, label: "50–99", color: "#0f766e" },
  { minimum: 100, label: "100–249", color: "#a16207" },
  { minimum: 250, label: "250–499", color: "#c2410c" },
  { minimum: 500, label: "500–1,499", color: "#b91c1c" },
  { minimum: 1_500, label: "≥ 1,500", color: "#7f1d1d" },
] as const;

const worldMapCssVariables = {
  "--map-background": WORLD_MAP_PALETTE.background,
  "--map-no-data": WORLD_MAP_PALETTE.noData,
  "--map-boundary": WORLD_MAP_PALETTE.boundary,
  "--map-quantitative-low": WORLD_MAP_PALETTE.quantitativeLow,
  "--map-quantitative-mid": WORLD_MAP_PALETTE.quantitativeMid,
  "--map-quantitative-high": WORLD_MAP_PALETTE.quantitativeHigh,
  "--map-delta-low": WORLD_MAP_PALETTE.deltaLow,
  "--map-delta-mid": WORLD_MAP_PALETTE.deltaMid,
  "--map-delta-high": WORLD_MAP_PALETTE.deltaHigh,
  "--map-withheld-base": WORLD_MAP_PALETTE.withheldBase,
  "--map-withheld-stripe": WORLD_MAP_PALETTE.withheldStripe,
  "--map-focus": WORLD_MAP_PALETTE.focus,
  "--map-label-accent": WORLD_MAP_PALETTE.labelAccent,
} as React.CSSProperties;

const globalFocusCountryCodes: ReadonlySet<string> = new Set(
  GLOBAL_FOCUS_COUNTRIES.map((country) => country.countryCode),
);
const mapGeometryCountryCodes: ReadonlySet<string> = new Set(
  [...mapData.countries, ...mapData.tinyCountries]
    .map((country) => country.countryCode)
    .filter((countryCode): countryCode is string => countryCode !== null),
);
const globalFocusCountriesWithoutGeometry = GLOBAL_FOCUS_COUNTRIES.filter(
  (country) => !mapGeometryCountryCodes.has(country.countryCode),
);
const globalFocusGeometryCount = GLOBAL_FOCUS_COUNTRIES.length
  - globalFocusCountriesWithoutGeometry.length;
const focusGeometryNote = `${globalFocusGeometryCount} collection targets have gold outlines. ${globalFocusCountriesWithoutGeometry.map((country) => country.countryName).join(", ")} ${globalFocusCountriesWithoutGeometry.length === 1 ? "is" : "are"} listed below but ${globalFocusCountriesWithoutGeometry.length === 1 ? "has" : "have"} no separate geometry in this map.`;

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
    return WORLD_COVERAGE_BANDS.reduce<string>(
      (color, band) => value >= band.minimum ? band.color : color,
      WORLD_COVERAGE_BANDS[0].color,
    );
  }

  if (metric === "delta") {
    const bounded = clamp(value, -0.05, 0.05);
    if (bounded <= 0) {
      return interpolateHex(
        WORLD_MAP_PALETTE.deltaLow,
        WORLD_MAP_PALETTE.deltaMid,
        (bounded + 0.05) / 0.05,
      );
    }
    return interpolateHex(
      WORLD_MAP_PALETTE.deltaMid,
      WORLD_MAP_PALETTE.deltaHigh,
      bounded / 0.05,
    );
  }

  const bounded = clamp(value, 0, 0.3);
  if (bounded <= 0.15) {
    return interpolateHex(
      WORLD_MAP_PALETTE.quantitativeLow,
      WORLD_MAP_PALETTE.quantitativeMid,
      bounded / 0.15,
    );
  }
  return interpolateHex(
    WORLD_MAP_PALETTE.quantitativeMid,
    WORLD_MAP_PALETTE.quantitativeHigh,
    (bounded - 0.15) / 0.15,
  );
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
  if (cell.hitRate !== null && cell.baselineRate === null) return "Observed sample";
  if (cell.state === "insufficient") return "No exact numerator";
  if (cell.state === "pending") return "Inference pending";
  if (cell.state === "anomaly") return "Possible anomaly";
  if (cell.state === "watch") return "Watch";
  return "Published";
}

export function WorldHeatmap({
  cells,
  coverageSummary,
  observations,
  initialMetric,
  compact = false,
}: {
  readonly cells: readonly CountryMapCell[];
  readonly coverageSummary: string;
  readonly observations: ObservationReadiness;
  readonly initialMetric?: WorldHeatMetric;
  readonly compact?: boolean;
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
  const titleId = `world-coverage-title-${instanceId}`;
  const withheldPatternId = `world-withheld-${instanceId}`;
  const focusCountries = GLOBAL_FOCUS_COUNTRIES.map((country) => {
    const row = cellsByCountry.get(country.countryCode);
    return {
      ...country,
      attribution: row === undefined
        ? null
        : formatCoverageAttribution(row.cell.coverageAttributionBases, "Country"),
      geometryAvailable: mapGeometryCountryCodes.has(country.countryCode),
      state: row === undefined
        ? "awaiting"
        : row.cell.hitRate !== null
          ? "published"
          : row.cell.state === "pending"
            ? "pending"
            : "observed",
    } as const;
  });
  const observedRateCount = cells.filter((cell) => cell.hitRate !== null).length;
  const publishedDeltaCount = cells.filter(
    (cell) => cell.deltaFromBaseline !== null,
  ).length;
  const noRateCount = rows.length - observedRateCount;
  const pendingCount = rows.filter(
    (row) => row.cell.hitRate === null && row.cell.state === "pending",
  ).length;
  const metricLabel = metric === "coverage"
    ? "Observed pack coverage"
    : metric === "delta"
      ? "Baseline delta"
      : "Observed sample rate";
  const period = observations.period
    ? `${formatDate(observations.period.start)} - ${formatDate(observations.period.end)}`
    : "No verified period yet";
  const readinessLabel = observations.status === "empty"
    ? "Awaiting observations"
    : observations.status === "collecting"
      ? "Collection in progress"
      : "Observed sample rates live";
  const mapDescription = rows.length === 0
    ? `No verified country or product-market coverage buckets are published. ${focusGeometryNote} Neutral fill does not contain inferred data.`
    : metric === "coverage"
      ? `${rows.length} country or product-market coverage buckets have verified pack-opening observations. Colour shows fixed-scale sample volume only, not a hit rate or representative demand. ${focusGeometryNote} Neutral fill means unobserved.`
      : metric === "rate"
        ? `${rows.length} country or product-market coverage buckets have verified observations: ${observedRateCount} show an exact observed sample rate and ${noRateCount} have no exact normalized numerator. ${focusGeometryNote} Neutral fill means unobserved.`
        : `${rows.length} country or product-market coverage buckets have verified observations: ${publishedDeltaCount} have a published baseline delta; raw sample rates remain separate from inference. ${focusGeometryNote} Neutral fill means unobserved.`;

  const selectMetric = (nextMetric: WorldHeatMetric) => {
    setMetric(nextMetric);
    const url = new URL(window.location.href);
    url.searchParams.set("metric", nextMetric);
    window.history.replaceState(null, "", `${url.pathname}${url.search}${url.hash}`);
  };

  const countryFill = (countryCode: string | null) => {
    if (!countryCode) return WORLD_MAP_PALETTE.noData;
    const row = cellsByCountry.get(countryCode);
    if (!row) return WORLD_MAP_PALETTE.noData;
    return row.status === "withheld" ? `url(#${withheldPatternId})` : row.fill;
  };

  const dataKeyClassName = metric === "delta"
    ? styles.deltaDataKey
    : styles.quantitativeDataKey;

  return (
    <section
      className={styles.atlas}
      aria-labelledby={titleId}
      style={worldMapCssVariables}
    >
      <header className={styles.header}>
        <div>
          <span className={styles.kicker}>Global evidence map</span>
          <h2 id={titleId}>
            {metric === "coverage" ? "Worldwide evidence coverage" : "Worldwide qualifying-hit map"}
          </h2>
          <p>
            {metric === "coverage"
              ? "Verified pack-opening sample volume by country or product-market coverage bucket. This view is not a hit-rate comparison."
              : metric === "rate"
                ? "Direct qualifying-hit counts divided by their exact eligible pack counts. These descriptive samples are not representative probabilities or predictions."
                : "Baseline comparisons are shown only after the separate inference publication gate. A raw observed sample rate does not automatically create a baseline delta."}
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
                  <rect width="7" height="7" fill={WORLD_MAP_PALETTE.withheldBase} />
                  <path d="M0 0V7" stroke={WORLD_MAP_PALETTE.withheldStripe} strokeWidth="2" />
                </pattern>
              </defs>
              <g aria-hidden="true">
                {mapData.countries.map((country, index) => {
                  const isFocusCountry = country.countryCode !== null
                    && globalFocusCountryCodes.has(country.countryCode);
                  const row = country.countryCode
                    ? cellsByCountry.get(country.countryCode)
                    : undefined;
                  return (
                    <path
                      className={`${styles.country} ${row ? styles.observedCountry : ""} ${isFocusCountry ? styles.focusCountry : ""}`}
                      d={country.path}
                      data-country-code={country.countryCode ?? undefined}
                      data-focus-country={isFocusCountry ? "true" : undefined}
                      fill={countryFill(country.countryCode)}
                      key={`${country.countryName}-${index}`}
                    />
                  );
                })}
                {mapData.tinyCountries.map((country, index) => {
                  const row = country.countryCode
                    ? cellsByCountry.get(country.countryCode)
                    : undefined;
                  const isFocusCountry = country.countryCode !== null
                    && globalFocusCountryCodes.has(country.countryCode);
                  const fill = row?.status === "withheld"
                      ? `url(#${withheldPatternId})`
                      : row
                        ? row.fill
                        : WORLD_MAP_PALETTE.noData;
                  return (
                    <circle
                      className={`${styles.tinyCountry} ${row ? styles.observedCountry : ""} ${isFocusCountry ? styles.focusCountry : ""}`}
                      cx={country.x}
                      cy={country.y}
                      data-country-code={country.countryCode ?? undefined}
                      data-focus-country={isFocusCountry ? "true" : undefined}
                      fill={fill}
                      key={`${country.countryName}-${index}`}
                      r={row ? 2.8 : 1.8}
                    />
                  );
                })}
              </g>
            </svg>
            {(metric === "coverage"
              ? rows.length === 0
              : metric === "rate"
                ? observedRateCount === 0
                : publishedDeltaCount === 0) ? (
              <div className={styles.emptyMapMessage} role="note">
                <strong>{metric === "coverage"
                  ? "No verified pack coverage yet"
                  : metric === "rate"
                    ? "No exact sample rates available yet"
                    : "No baseline deltas published yet"}</strong>
                <span>{rows.length === 0
                  ? "Gold outlines mark collection focus; fill remains reserved for verified evidence."
                  : pendingCount > 0
                    ? `${rows.length} ${rows.length === 1 ? "coverage bucket is" : "coverage buckets are"} observed; ${pendingCount} ${pendingCount === 1 ? "has" : "have"} no published inference yet.`
                    : metric === "rate"
                      ? `${rows.length} ${rows.length === 1 ? "coverage bucket has" : "coverage buckets have"} observations, but no exact normalized numerator is available.`
                      : "Direct sample rates and baseline inference are published independently."}</span>
              </div>
            ) : null}
          </div>

          <figcaption className={styles.caption}>
            <div className={styles.legend} role="group" aria-label={`${metricLabel} map legend`}>
              {metric === "coverage" ? (
                <>
                  <span>Observed packs</span>
                  <ul className={styles.coverageBands} aria-label="Fixed pack-count colour bands">
                    {WORLD_COVERAGE_BANDS.map((band) => (
                      <li key={band.minimum}><i style={{ backgroundColor: band.color }} aria-hidden="true" /><span>{band.label}</span></li>
                    ))}
                  </ul>
                </>
              ) : <>
              <span
                className={`${styles.legendScale} ${metric === "delta" ? styles.deltaScale : styles.rateScale}`}
                aria-hidden="true"
              />
              <span className={styles.legendTicks}>
                {metric === "delta" ? (
                  <><span>≤ −5 pp</span><span>0 pp</span><span>≥ +5 pp</span></>
                ) : (
                  <><span>0%</span><span>15%</span><span>≥ 30%</span></>
                )}
              </span>
              </>}
              <span className={styles.legendKeys}>
                <span className={styles.noDataKey}><i aria-hidden="true" />Not observed</span>
                <span className={styles.focusKey}><i aria-hidden="true" />Collection focus, awaiting observations</span>
                {metric === "coverage" ? null : metric === "rate" ? (
                  <>
                    <span className={styles.withheldKey}><i aria-hidden="true" />Observed, no exact numerator</span>
                    <span className={styles.publishedKey}><i className={dataKeyClassName} aria-hidden="true" />Observed sample rate uses scale</span>
                  </>
                ) : (
                  <>
                    <span className={styles.withheldKey}><i aria-hidden="true" />No published baseline delta</span>
                    <span className={styles.publishedKey}><i className={dataKeyClassName} aria-hidden="true" />Published baseline delta uses scale</span>
                  </>
                )}
              </span>
            </div>
            <p id={`world-map-caveat-${instanceId}`}>
              {metric === "coverage"
                ? `Fixed absolute pack-count colour bands; never rescaled to the current snapshot. This shows sample volume, not a hit rate or representative demand. ${focusGeometryNote} Neutral fill means unobserved.`
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
            <div><dt>Coverage buckets observed</dt><dd>{integer.format(observations.countriesObserved)}</dd></div>
            <div><dt>Observed sample rates</dt><dd>{integer.format(observations.countriesWithPublishedRate)}</dd></div>
            <div><dt>Observed packs</dt><dd>{integer.format(observations.observedPacks)}</dd></div>
            <div><dt>Complete openings</dt><dd>{integer.format(observations.completeOpenings)}</dd></div>
          </dl>
          <p className={styles.coverageSummary}>{coverageSummary}</p>
          <p className={styles.sourceNote}>{observations.sourceCountryContributions === 0
            ? "No verified source-attribution contributions have reached publication yet."
            : `${integer.format(observations.sourceCountryContributions)} source-attribution contributions. A source may appear in more than one coverage bucket, so this is not a global independent-source count.`}
          </p>
          <p className="sr-only" role="status" aria-live="polite">
            {metricLabel} selected. The world map has updated.
          </p>
        </aside>
      </div>

      <details className={styles.details} open={compact ? undefined : true}>
        <summary>Country and market details <span>{rows.length} observed buckets · exact values and collection status</span></summary>
      <section className={styles.focusBlock} aria-labelledby={`collection-focus-${instanceId}`}>
        <div className={styles.focusHeading}>
          <div>
            <span>Expanded collection focus</span>
            <h3 id={`collection-focus-${instanceId}`}>Countries / product markets</h3>
          </div>
          <p>The map visualises fixed-scale verified metrics where available. This list shows collection status; the table provides exact values. Hong Kong remains listed but has no separate geometry in this map.</p>
        </div>
        <ul className={styles.focusList} aria-label="Countries and product markets in the expanded collection focus">
          {focusCountries.map((country) => (
            <li key={country.countryCode}>
              <i className={styles[`focus${country.state}`]} aria-hidden="true" />
              <span>
                <strong>{country.countryName}</strong>
                <small>{country.countryCode} · {country.state === "published"
                  ? "Sample rate available"
                  : country.state === "pending"
                    ? "Inference pending"
                  : country.state === "observed"
                    ? "Sample observed"
                    : "Awaiting observations"}</small>
                {country.attribution === null ? null : (
                  <small>Attribution · {country.attribution}</small>
                )}
                {country.geometryAvailable ? null : (
                  <small>List/table only · no separate map geometry</small>
                )}
              </span>
            </li>
          ))}
        </ul>
      </section>

      <div className={styles.tableBlock}>
        <div className={styles.tableHeading}>
          <strong>Country / product-market coverage</strong>
          <small>Alphabetical, not a ranking</small>
        </div>
        <div className={styles.tableFrame} role="region" aria-label="Exact country and product-market coverage values" tabIndex={0}>
          <table>
            <caption className="sr-only">Exact country and product-market coverage values for {period}</caption>
            <thead>
              <tr><th scope="col">Bucket</th><th scope="col">Packs</th><th scope="col">Sources</th><th scope="col">Data version</th><th scope="col">Hits / rate packs</th><th scope="col">Sample rate</th><th scope="col">Baseline</th><th scope="col">Delta</th><th scope="col">Status</th></tr>
            </thead>
            <tbody>
              {rows.length === 0 ? (
                <tr><td colSpan={9} className={styles.empty}>No verified country or product-market coverage is published yet.</td></tr>
              ) : rows.map((row) => (
                <tr key={row.cell.countryCode}>
                  <td data-label="Bucket"><strong>{row.cell.countryName}</strong><small>{row.cell.countryCode} · {formatCoverageAttribution(row.cell.coverageAttributionBases, "Country")}</small></td>
                  <td data-label="Packs">{integer.format(row.cell.packsObserved)}</td>
                  <td data-label="Sources">{integer.format(row.cell.independentSources)}</td>
                  <td className={styles.dataVersionCell} data-label="Data version">
                    {row.cell.dataVersions === undefined ? (
                      <span className={styles.dataVersionEmpty}>Not provided</span>
                    ) : (
                      <span className={styles.dataVersionList}>
                        {row.cell.dataVersions.map((version) => {
                          const lang = sourceNativeLanguageTag(version);
                          return (
                            <span
                              className={styles.dataVersion}
                              dir="auto"
                              key={version}
                              {...(lang === undefined ? {} : { lang })}
                            >
                              {version}
                            </span>
                          );
                        })}
                      </span>
                    )}
                  </td>
                  <td data-label="Hits / rate packs">{row.cell.ratePacksObserved === undefined || row.cell.qualifyingHitPacks === undefined
                    ? "Not available"
                    : `${integer.format(row.cell.qualifyingHitPacks)} / ${integer.format(row.cell.ratePacksObserved)}`}</td>
                  <td data-label="Sample rate">{formatProbability(row.cell.hitRate)}</td>
                  <td data-label="Baseline">{formatProbability(row.cell.baselineRate)}</td>
                  <td data-label="Delta">{formatSignedProbability(row.cell.deltaFromBaseline)}</td>
                  <td data-label="Status"><span className={`${styles.status} ${styles[`status${row.cell.state}`]}`}>{stateLabel(row.cell)}</span></td>
                </tr>
              ))}
            </tbody>
          </table>
        </div>
      </div>
      </details>
    </section>
  );
}
