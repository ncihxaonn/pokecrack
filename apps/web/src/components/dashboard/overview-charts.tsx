"use client";

import React, { useState } from "react";
import type { ObservationReadiness } from "@/data/types";
import { coverageBands, coverageDistribution, logPosition, rankCoverage, volumeSplit, type CoverageBand, type CoverageMetric, type CoverageRow } from "@/lib/overview-charts";
import styles from "./overview-charts.module.css";

const integer = new Intl.NumberFormat("en-AU");
const percent = new Intl.NumberFormat("en-AU", { style: "percent", maximumFractionDigits: 1 });
const tones = ["#7f4bf3", "#1f1f1f", "#7768ce", "#cc795f"];

function MetricSwitch({ value, onChange, label }: { value: CoverageMetric; onChange: (value: CoverageMetric) => void; label: string }) {
  return <div className={styles.switch} role="group" aria-label={label}>
    {(["packs", "openings"] as const).map((metric) => <button type="button" key={metric} aria-pressed={value === metric} onClick={() => onChange(metric)}>{metric === "packs" ? "Packs" : "Openings"}</button>)}
  </div>;
}

export function OverviewCharts({ rows, observations }: { rows: readonly CoverageRow[]; observations: ObservationReadiness }) {
  const [metric, setMetric] = useState<CoverageMetric>("packs");
  const [splitMetric, setSplitMetric] = useState<CoverageMetric>("packs");
  const [query, setQuery] = useState("");
  const [band, setBand] = useState<CoverageBand>("all");
  const [limit, setLimit] = useState(10);
  const [selected, setSelected] = useState<string | null>(null);
  const [pointerMotion, setPointerMotion] = useState(false);
  const ranked = rankCoverage(rows, metric, query, band);
  const visible = ranked.slice(0, limit);
  const active = ranked.find((row) => row.code === selected) ?? ranked[0];
  const ceiling = Math.max(1, ...ranked.map((row) => row[metric]));
  const distribution = coverageDistribution(rows);
  const bandCeiling = Math.max(1, ...distribution.map((item) => item.count));
  const split = volumeSplit(observations, splitMetric);
  const maxPacks = Math.max(1, ...ranked.map((row) => row.packs));
  const maxOpenings = Math.max(1, ...ranked.map((row) => row.openings));

  return <section className={styles.section} aria-labelledby="highlights-title" data-pointer-motion={pointerMotion} onPointerDownCapture={() => setPointerMotion(true)} onKeyDownCapture={() => setPointerMotion(false)}>
    <div className={styles.heading}>
      <div><h2 id="highlights-title">Explore the numbers</h2><p>Compare the data already collected. Select a country or market to inspect its counts.</p></div>
      <span className={styles.scope}>{integer.format(rows.length)} published buckets</span>
    </div>
    <div className={styles.grid}>
      <article className={`${styles.card} ${styles.ranking}`} aria-labelledby="ranking-title">
        <div className={styles.cardHeading}><h3 id="ranking-title">Country &amp; market ranking</h3><MetricSwitch value={metric} onChange={setMetric} label="Ranking metric" /></div>
        <p className={styles.note}>Published country / product-market counts, not a ranking of pull odds.</p>
        <div className={styles.filters}>
          <label><span className="sr-only">Find a country or market</span><input type="search" value={query} onChange={(event) => setQuery(event.target.value)} placeholder="Find a country or market" /></label>
          <label><span className="sr-only">Ranking length</span><select value={limit} onChange={(event) => setLimit(Number(event.target.value))}><option value={10}>Top 10</option><option value={20}>Top 20</option><option value={249}>All</option></select></label>
        </div>
        {band !== "all" ? <button className={styles.clear} type="button" onClick={() => setBand("all")}>{coverageBands.find((item) => item.id === band)?.label} · Clear filter ×</button> : null}
        <div className={styles.rankingScroll}>
          {visible.length === 0 ? <p className={styles.empty}>No published buckets match these filters.</p> : <ol className={styles.bars} aria-label={`Country ranking by ${metric}`}>
            {visible.map((row, index) => <li key={row.code}>
              <button type="button" className={styles.barRow} aria-pressed={active?.code === row.code} onClick={() => setSelected(row.code)}>
                <span className={styles.rank}>{index + 1}</span><span className={styles.countryName}>{row.name}</span><strong>{integer.format(row[metric])}</strong>
                <span className={styles.track} aria-hidden="true"><span style={{ transform: `scaleX(${row[metric] / ceiling})`, backgroundColor: tones[index % tones.length] }} /></span>
              </button>
            </li>)}
          </ol>}
        </div>
        <p className={styles.note}>{visible.length} of {ranked.length} matching buckets · {metric === "packs" ? "Pack counts" : "Opening records"}</p>
      </article>

      <article className={styles.card} aria-labelledby="volume-title">
        <div className={styles.cardHeading}><h3 id="volume-title">Global volume</h3><MetricSwitch value={splitMetric} onChange={setSplitMetric} label="Global volume metric" /></div>
        <p className={styles.note}>Where a country or market attribution is available.</p>
        {split === null ? <p className={styles.empty}>No location breakdown is published for this snapshot.</p> : <>
          <div className={styles.donutWrap}>
            <svg viewBox="0 0 180 180" className={styles.donut} role="img" aria-label={`${integer.format(split.attributed)} attributed ${splitMetric}; ${integer.format(split.unknown)} ${splitMetric} with unknown location`}>
              <circle cx="90" cy="90" r="68" fill="none" stroke="#e7e7e7" strokeWidth="20" />
              <circle cx="90" cy="90" r="68" fill="none" stroke="#7f4bf3" strokeWidth="20" pathLength="100" strokeDasharray={`${split.attributed / split.total * 100} 100`} transform="rotate(-90 90 90)" />
            </svg>
            <div className={styles.donutLabel}><strong>{integer.format(split.total)}</strong><span>{splitMetric === "packs" ? "published packs" : "opening records"}</span></div>
          </div>
          <dl className={styles.legend}>
            <div><dt><i style={{ background: "#7f4bf3" }} />Country / market attributed</dt><dd>{integer.format(split.attributed)} <small>{percent.format(split.attributed / split.total)}</small></dd></div>
            <div><dt><i style={{ background: "#e7e7e7" }} />Location unknown</dt><dd>{integer.format(split.unknown)} <small>{percent.format(split.unknown / split.total)}</small></dd></div>
          </dl>
          <p className={styles.note}>Unknown-location volume stays in the total, not on the country map.</p>
        </>}
      </article>

      <article className={styles.card} aria-labelledby="depth-title">
        <div className={styles.cardHeading}><h3 id="depth-title">Coverage depth</h3><span className={styles.scope}>Buckets, not packs</span></div>
        <p className={styles.note}>Select a pack range to filter the country charts.</p>
        <div className={styles.depthBars} role="group" aria-label="Filter countries by pack count">
          {distribution.map((item, index) => <button type="button" key={item.id} aria-pressed={band === item.id} onClick={() => setBand(band === item.id ? "all" : item.id)}>
            <span>{item.label}</span><strong>{item.count}</strong>
            <span className={styles.depthTrack} aria-hidden="true"><span style={{ transform: `scaleX(${item.count / bandCeiling})`, backgroundColor: tones[index] }} /></span>
          </button>)}
        </div>
        <p className={styles.note}>A zero means no published bucket in that range, not zero openings worldwide.</p>
      </article>

      <article className={styles.card} aria-labelledby="comparison-title">
        <div className={styles.cardHeading}><h3 id="comparison-title">Packs &amp; opening records</h3><span className={styles.scope}>Log scale</span></div>
        <p className={styles.note}>Each dot is a country / market bucket. Tap or focus one to inspect it.</p>
        {ranked.length === 0 ? <p className={styles.empty}>No published buckets match these filters.</p> : <>
          <div className={styles.scatter} role="group" aria-label="Country pack and opening comparison">
            <span className={styles.yMax}>{integer.format(maxOpenings)} openings</span>
            <span className={styles.origin}>0</span><span className={styles.xMax}>{integer.format(maxPacks)} packs</span>
            <div className={styles.plot}>
              {ranked.map((row) => <button type="button" key={row.code} className={styles.dot} aria-label={`${row.name}: ${integer.format(row.packs)} packs, ${integer.format(row.openings)} openings`} aria-pressed={active?.code === row.code} title={`${row.name} · ${integer.format(row.packs)} packs · ${integer.format(row.openings)} openings`} style={{ left: `${logPosition(row.packs, maxPacks) * 100}%`, bottom: `${logPosition(row.openings, maxOpenings) * 100}%` }} onClick={() => setSelected(row.code)} onFocus={() => setSelected(row.code)}><span /></button>)}
            </div>
          </div>
          {active ? <div className={styles.selection} aria-live="polite" aria-atomic="true">
            <strong>{active.name}</strong><span>{integer.format(active.packs)} packs · {integer.format(active.openings)} openings</span><small>{active.attribution}</small>
          </div> : null}
        </>}
      </article>
    </div>
  </section>;
}
