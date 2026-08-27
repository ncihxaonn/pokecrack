import React from "react";
import type { Route } from "next";
import Link from "next/link";
import { Barcode, CircleCheckBig, Layers, MapPinned, PackageOpen, ScanSearch } from "lucide-react";

import { BRAND } from "@/config/brand";
import type { PublicDashboardData } from "@/data/types";
import { formatDateTime, formatProbability } from "@/lib/format";
import { TrendChart } from "@/components/charts/trend-chart";
import { RegionHeatmap } from "./region-heatmap";
import { DataModeNotice, MetricDisclaimer, Panel, SectionHeading, SignalBadge, TableFrame } from "@/components/ui/dashboard-ui";

const integer = new Intl.NumberFormat("en-AU");

export function HomeView({ data, synthetic }: { data: PublicDashboardData; synthetic: boolean }) {
  const trending = [...data.sets]
    .sort((left, right) => right.packsObserved - left.packsObserved)
    .slice(0, 4);
  const watched = data.sets.filter((set) => set.state === "watch" || set.state === "anomaly");

  return (
    <div className="page-shell home-page">
      <section className="dashboard-intro" aria-labelledby="hero-title">
        <div>
          <span className="eyebrow">Australia · observed activity · {data.summary.methodologyVersion}</span>
          <h1 id="hero-title">{BRAND.tagline}</h1>
          <p>{BRAND.description}</p>
        </div>
        <div className="dashboard-intro__actions">
          <Link className="button" href="/sets">Explore sets <span aria-hidden="true">↗</span></Link>
          <Link className="button button--secondary" href="/methodology">How we measure</Link>
        </div>
      </section>

      <RegionHeatmap regions={data.regions} />
      <DataModeNotice synthetic={synthetic} generatedAt={data.generatedAt} />

      <dl className="stat-grid stat-grid--summary" aria-label="Dashboard totals">
        <div><dt><span className="stat-icon stat-icon--blue" aria-hidden="true"><PackageOpen size={19} /></span>Observed Packs</dt><dd>{integer.format(data.summary.observedPacks)}<small>eligible denominator</small></dd></div>
        <div><dt><span className="stat-icon stat-icon--violet" aria-hidden="true"><CircleCheckBig size={19} /></span>Complete Openings</dt><dd>{integer.format(data.summary.completeOpenings)}<small>validated observations</small></dd></div>
        <div><dt><span className="stat-icon stat-icon--pink" aria-hidden="true"><ScanSearch size={19} /></span>AI-Validated Sources</dt><dd>{integer.format(data.summary.aiValidatedSources)}<small>aggregate source count</small></dd></div>
        <div><dt><span className="stat-icon stat-icon--green" aria-hidden="true"><Layers size={19} /></span>Tracked Sets</dt><dd>{integer.format(data.summary.trackedSets)}<small>published aggregates</small></dd></div>
        <div><dt><span className="stat-icon stat-icon--amber" aria-hidden="true"><MapPinned size={19} /></span>Tracked Regions</dt><dd>{integer.format(data.summary.trackedRegions)}<small>Australian coverage</small></dd></div>
        <div><dt><span className="stat-icon stat-icon--ink" aria-hidden="true"><Barcode size={19} /></span>Batch Sightings</dt><dd>{integer.format(data.summary.batchSightings)}<small>visible labels only</small></dd></div>
      </dl>

      <section className="dashboard-section" aria-labelledby="trend-title">
        <SectionHeading id="trend-title" title="Observed trend" detail="Weekly aggregate and rolling baseline; a visual aid with a textual table below." />
        <Panel className="trend-panel">
          <TrendChart points={data.trend} />
          <TableFrame label="Observed trend values">
            <table>
              <thead><tr><th>Date</th><th>Observed</th><th>Baseline</th><th>Packs</th></tr></thead>
              <tbody>{data.trend.map((point) => <tr key={point.date}><td>{point.date}</td><td>{formatProbability(point.observedRate)}</td><td>{formatProbability(point.baselineRate)}</td><td>{integer.format(point.packsObserved)}</td></tr>)}</tbody>
            </table>
          </TableFrame>
        </Panel>
      </section>

      <div className="dashboard-split">
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
      </div>

      <section className="dashboard-section" aria-labelledby="activity-title">
        <SectionHeading id="activity-title" title="Recent observed activity" detail="Published source activity can include entries that are not statistically eligible." />
        <Panel>
          <TableFrame label="Recent observed activity">
            <table>
              <thead><tr><th>Observed</th><th>Source</th><th>Set / product</th><th>Region</th><th>Evidence</th></tr></thead>
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
      </section>

      <section className="dashboard-section methodology-glance" aria-labelledby="methodology-title">
        <SectionHeading id="methodology-title" title="Methodology at a glance" detail="Conservative publication thresholds keep incomplete observations out of rate denominators." />
        <div className="method-steps">
          {[
            ["01", "Collect", "Allowlisted, bounded discovery and metadata only."],
            ["02", "Validate", "Complete, nonduplicate tier A/B observations qualify."],
            ["03", "Aggregate", "Packs observed form the denominator; no missing counts are imputed."],
            ["04", "Publish", "Intervals, sample sizes, freshness and restrained signal labels."],
          ].map(([number, title, detail]) => <Panel key={number}><span>{number}</span><h3>{title}</h3><p>{detail}</p></Panel>)}
        </div>
        <Link className="button button--secondary" href="/methodology">Full methodology</Link>
      </section>

      <MetricDisclaimer />
    </div>
  );
}
