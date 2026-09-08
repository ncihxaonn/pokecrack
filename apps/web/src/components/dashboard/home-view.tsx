import React from "react";
import type { Route } from "next";
import Link from "next/link";

import type { WorldHeatMetric } from "@/app/_lib/world-map-query";
import type { PublicDashboardData } from "@/data/types";
import { formatDate, formatDateTime, formatProbability } from "@/lib/format";
import { TrendChart } from "@/components/charts/trend-chart";
import { WorldHeatmap } from "./world-heatmap";
import { OverviewHighlights } from "./overview-highlights";
import { DataModeNotice, MetricDisclaimer, Panel, SectionHeading, SignalBadge, TableFrame } from "@/components/ui/dashboard-ui";

const integer = new Intl.NumberFormat("en-AU");

export function HomeView({ data, synthetic, worldMetric }: { data: PublicDashboardData; synthetic: boolean; worldMetric?: WorldHeatMetric }) {
  const trending = [...data.sets]
    .sort((left, right) => right.packsObserved - left.packsObserved)
    .slice(0, 4);
  const watched = data.sets.filter((set) => set.state === "watch" || set.state === "anomaly");
  const catalogPreview = data.catalog.sets.slice(0, 8);
  const modeNotice = <DataModeNotice
    catalogSetCount={data.catalog.setCount}
    generatedAt={data.generatedAt}
    observationStatus={data.observations.status}
    observedCountryCount={data.observations.countriesObserved}
    observedPackCount={data.observations.observedPacks}
    synthetic={synthetic}
  />;

  return (
    <div className="page-shell home-page">
      {/* Synthetic provenance must precede the map and all other metrics. */}
      {synthetic ? modeNotice : null}
      <section className="dashboard-intro" aria-labelledby="hero-title">
        <div className="dashboard-intro__copy">
          <h1 id="hero-title">Pokémon opening analysis</h1>
          <p>Explore Pokémon TCG opening data across sets, countries and product markets.</p>
        </div>
      </section>

      <div id="world-coverage"><WorldHeatmap
        cells={data.mapCells}
        coverageSummary={data.summary.globalCoverage}
        observations={data.observations}
        initialMetric={worldMetric}
        compact
      /></div>

      <div className="analysis-layout">
        <nav className="analysis-nav" aria-label="On this page">
          <a href="#world-coverage">World coverage</a>
          <a href="#highlights-title">Highlights</a>
          <a href="#catalog-title">Set catalog</a>
          {data.trend.length > 0 ? <a href="#trend-title">Observed trend</a> : null}
          {trending.length > 0 || watched.length > 0 ? <a href="#trending-title">Set comparisons</a> : null}
          {data.recentActivity.length > 0 ? <a href="#activity-title">Recent activity</a> : null}
        </nav>
        <div className="analysis-content">
      {synthetic ? null : modeNotice}
      <dl className="stat-grid stat-grid--summary" aria-label="Global dashboard totals">
        <div><dt>Observed packs</dt><dd>{integer.format(data.observations.observedPacks)}<small>Verified eligible denominator</small></dd></div>
        <div><dt>Complete openings</dt><dd>{integer.format(data.observations.completeOpenings)}<small>Reviewed observations</small></dd></div>
        <div><dt>Coverage buckets</dt><dd>{integer.format(data.observations.countriesObserved)}<small>Countries or product markets</small></dd></div>
        <div><dt>Catalog sets</dt><dd>{integer.format(data.catalog.setCount)}<small>Metadata, not opening evidence</small></dd></div>
      </dl>
      <OverviewHighlights data={data} />

      <section className="dashboard-section" aria-labelledby="catalog-title">
        <SectionHeading
          id="catalog-title"
          title="Global set catalog"
          detail={`${data.catalog.name} metadata for discovery — never opening evidence or a pull-rate denominator.`}
        />
        <Panel className="catalog-panel">
          <TableFrame label="Global TCGdex set catalog preview">
            <table>
              <thead><tr><th scope="col">Set</th><th scope="col">Series</th><th scope="col">Release</th><th scope="col">Language</th></tr></thead>
              <tbody>
                {catalogPreview.length === 0 ? (
                  <tr><td colSpan={4} className="empty-cell">No current catalog sets are available.</td></tr>
                ) : catalogPreview.map((set) => (
                  <tr key={set.id}>
                    <td data-label="Set"><strong>{set.name}</strong><small>{set.slug}</small></td>
                    <td data-label="Series">{set.series ?? "Unspecified"}</td>
                    <td data-label="Release">{set.releaseDate ? formatDate(set.releaseDate) : "Unscheduled"}</td>
                    <td data-label="Language">{set.language.toUpperCase()}</td>
                  </tr>
                ))}
              </tbody>
            </table>
          </TableFrame>
          <p className="catalog-footnote">
            Showing {integer.format(catalogPreview.length)} of {integer.format(data.catalog.setCount)} current sets. Last checked {formatDateTime(data.catalog.lastCheckedAt)}.
          </p>
        </Panel>
      </section>

      {data.trend.length > 0 ? <section className="dashboard-section" aria-labelledby="trend-title">
        <SectionHeading id="trend-title" title="Observed trend" detail="Weekly aggregate and rolling baseline; a visual aid with a textual table below." />
        <Panel className="trend-panel">
          <TrendChart points={data.trend} />
          <TableFrame label="Observed trend values">
            <table>
              <thead><tr><th scope="col">Date</th><th scope="col">Observed</th><th scope="col">Baseline</th><th scope="col">Packs</th></tr></thead>
              <tbody>{data.trend.map((point) => <tr key={point.date}><td>{point.date}</td><td>{formatProbability(point.observedRate)}</td><td>{formatProbability(point.baselineRate)}</td><td>{integer.format(point.packsObserved)}</td></tr>)}</tbody>
            </table>
          </TableFrame>
        </Panel>
      </section> : null}

      {trending.length > 0 || watched.length > 0 ? <div className="dashboard-split">
        <section className="dashboard-section" aria-labelledby="trending-title">
          <SectionHeading id="trending-title" title="Trending sets" detail="Ordered by observed sample volume, not expected outcomes." action={<Link className="text-link" href="/sets">All sets →</Link>} />
          <Panel>
            {trending.length === 0 ? <p className="empty-cell">No set aggregates are published.</p> : <ol className="rank-list">
              {trending.map((set, index) => (
                <li key={set.slug}>
                  <span className="rank-list__number">{String(index + 1).padStart(2, "0")}</span>
                  <Link href={`/sets/${set.slug}` as Route}><strong>{set.name}</strong><small>{integer.format(set.packsObserved)} packs · {formatProbability(set.hitRate)}</small></Link>
                  <SignalBadge metric={set} />
                </li>
              ))}
            </ol>}
          </Panel>
        </section>

        <section className="dashboard-section" aria-labelledby="watch-title">
          <SectionHeading id="watch-title" title="Signal watch" detail="Exploratory thresholds only; causal interpretation is not supported." />
          <Panel>
            {watched.length === 0 ? <p className="empty-cell">No watch signals are published in this snapshot.</p> : <ul className="watch-list">
              {watched.map((set) => (
                <li key={set.slug}><div><Link href={`/sets/${set.slug}` as Route}>{set.name}</Link><small>{set.sampleNote}</small></div><SignalBadge metric={set} /></li>
              ))}
            </ul>}
          </Panel>
        </section>
      </div> : null}

      {data.recentActivity.length > 0 ? <section className="dashboard-section" aria-labelledby="activity-title">
        <SectionHeading id="activity-title" title="Recent observed activity" detail="Published source activity can include entries that are not statistically eligible." />
        <Panel>
          <TableFrame label="Recent observed activity">
            <table>
              <thead><tr><th scope="col">Observed</th><th scope="col">Source</th><th scope="col">Set / product</th><th scope="col">Region</th><th scope="col">Evidence</th></tr></thead>
              <tbody>
                {data.recentActivity.length === 0 ? <tr><td colSpan={5} className="empty-cell">No recent public activity is available.</td></tr> : data.recentActivity.map((activity) => (
                  <tr key={activity.id}>
                    <td><time dateTime={activity.observedAt}>{formatDateTime(activity.observedAt)}</time></td>
                    <td><a className="external-link" href={activity.sourceUrl} target="_blank" rel="noopener noreferrer">{activity.platform}<span className="sr-only"> (opens in a new tab)</span></a></td>
                    <td><strong>{activity.setName}</strong><small>{activity.productType} · {activity.packCount} packs</small></td>
                    <td>{activity.region}<small>{activity.retailer}</small></td>
                    <td><span className={`eligibility eligibility--${activity.statisticsEligible ? "eligible" : "activity"}`}>{activity.statisticsEligible ? `Tier ${activity.evidenceTier}` : "Activity only"}</span></td>
                  </tr>
                ))}
              </tbody>
            </table>
          </TableFrame>
        </Panel>
      </section> : null}

      <MetricDisclaimer />
        </div>
      </div>
    </div>
  );
}
