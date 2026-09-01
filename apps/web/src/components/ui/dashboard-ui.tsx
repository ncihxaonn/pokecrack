import React, { type ReactNode } from "react";

import { BRAND } from "@/config/brand";
import type { ObservedMetric } from "@/data/types";
import { formatCompactNumber, formatDateTime, formatProbability, formatSignedProbability } from "@/lib/format";
import { getSignalPresentation } from "@/lib/signals";

export function PageIntro({ eyebrow, title, description, children }: { eyebrow: string; title: string; description: string; children?: ReactNode }) {
  return (
    <header className="page-intro">
      <span className="eyebrow">{eyebrow}</span>
      <h1>{title}</h1>
      <p>{description}</p>
      {children}
    </header>
  );
}

export function SectionHeading({ id, title, detail, action }: { id?: string; title: string; detail?: string; action?: ReactNode }) {
  return (
    <div className="section-heading">
      <div><h2 id={id}>{title}</h2>{detail ? <p>{detail}</p> : null}</div>
      {action}
    </div>
  );
}

export function Panel({ children, className = "" }: { children: ReactNode; className?: string }) {
  return <div className={`panel ${className}`.trim()}>{children}</div>;
}

const integer = new Intl.NumberFormat("en-AU");

export function DataModeNotice({
  synthetic,
  generatedAt,
  catalogSetCount,
  observationStatus,
  observedCountryCount,
  observedPackCount,
}: {
  synthetic: boolean;
  generatedAt: string;
  catalogSetCount?: number;
  observationStatus?: "empty" | "collecting" | "published";
  observedCountryCount?: number;
  observedPackCount?: number;
}) {
  const catalogOnly = !synthetic && observationStatus === "empty";
  const collecting = !synthetic && observationStatus === "collecting";
  const label = synthetic ? "Synthetic demo" : collecting ? "Live observations" : catalogOnly ? "Live catalog" : "Live snapshot";
  const message = synthetic
    ? BRAND.demoNotice
    : collecting
      ? `Verified observations cover ${integer.format(observedCountryCount ?? 0)} countries and ${integer.format(observedPackCount ?? 0)} packs; country-level rates remain withheld until evidence thresholds and reviewed publication are satisfied.`
      : catalogOnly
        ? `${integer.format(catalogSetCount ?? 0)} catalog sets are live. Verified country observations are not published yet.`
        : "Live response with no demo fixtures.";

  return (
    <aside className={`mode-notice ${synthetic ? "mode-notice--demo" : "mode-notice--live"}`} aria-label="Data provenance">
      <span className="mode-notice__label">{label}</span>
      <p>{message}</p>
      <time dateTime={generatedAt}>Snapshot {formatDateTime(generatedAt)}</time>
    </aside>
  );
}

export function PublicUnavailable({ title, message, code }: { title: string; message: string; code: string }) {
  return (
    <section className="page-shell state-page" aria-labelledby="unavailable-title">
      <span className="status-code">LIVE_{code.replaceAll("-", "_").toUpperCase()}</span>
      <h1 id="unavailable-title">{title}</h1>
      <p>{message}</p>
      <p className="muted">This live response contains no synthetic fallback data.</p>
    </section>
  );
}

export function MetricDisclaimer({ batch = false }: { batch?: boolean }) {
  return (
    <aside className="disclaimer" aria-label="Observation disclaimer">
      <p>{BRAND.individualPackDisclaimer}</p>
      {batch ? <p>{BRAND.batchDisclaimer}</p> : null}
    </aside>
  );
}

export function SignalBadge({ metric }: { metric: Pick<ObservedMetric, "state"> }) {
  const signal = getSignalPresentation(metric.state);
  return <span aria-label={`${signal.label}. ${signal.detail}`} className={`signal signal--${signal.tone}`} title={signal.detail}>{signal.label}</span>;
}

export function ObservationStats({ metric }: { metric: ObservedMetric }) {
  const interval = metric.credibleInterval
    ? `${formatProbability(metric.credibleInterval.low)} to ${formatProbability(metric.credibleInterval.high)}`
    : "Withheld";
  return (
    <dl className="stat-grid stat-grid--detail">
      <div><dt>Packs observed</dt><dd>{formatCompactNumber(metric.packsObserved)}</dd></div>
      <div><dt>Complete openings</dt><dd>{formatCompactNumber(metric.openings)}</dd></div>
      <div><dt>Independent sources</dt><dd>{formatCompactNumber(metric.independentSources)}</dd></div>
      <div><dt>Baseline rate</dt><dd>{formatProbability(metric.baselineRate)}</dd></div>
      <div><dt>Observed rate</dt><dd>{formatProbability(metric.hitRate)}</dd></div>
      <div><dt>Posterior mean</dt><dd>{formatProbability(metric.posteriorMean)}</dd></div>
      <div><dt>90% interval</dt><dd>{interval}</dd></div>
      <div><dt>From baseline</dt><dd>{formatSignedProbability(metric.deltaFromBaseline)}</dd></div>
      <div><dt>Signal</dt><dd><SignalBadge metric={metric} /></dd></div>
    </dl>
  );
}

export function TableFrame({ children, label }: { children: ReactNode; label: string }) {
  return <div className="table-frame" role="region" aria-label={label} tabIndex={0}>{children}</div>;
}

export function EmptyTableRow({ columns, message }: { columns: number; message: string }) {
  return <tr><td className="empty-cell" colSpan={columns}>{message}</td></tr>;
}

export function DefinitionList({ items }: { items: readonly { term: string; value: ReactNode }[] }) {
  return (
    <dl className="definition-list">
      {items.map((item) => <div key={item.term}><dt>{item.term}</dt><dd>{item.value}</dd></div>)}
    </dl>
  );
}
