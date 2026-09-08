import React from "react";
import type { PublicDashboardData } from "@/data/types";

const integer = new Intl.NumberFormat("en-AU");
type Bar = { key: string; label: string; value: number };

// Each chart ranks its own published buckets. It never sums potentially
// overlapping geographic attributions into a new global denominator.
function HighlightChart({ title, detail, tone, rows }: {
  title: string; detail: string; tone: "violet" | "yellow" | "orange"; rows: readonly Bar[];
}) {
  const ranked = [...rows].filter((row) => row.value > 0)
    .sort((a, b) => b.value - a.value || a.label.localeCompare(b.label)).slice(0, 5);
  const ceiling = Math.max(1, ...ranked.map((row) => row.value));
  return (
    <article className={`highlight-card highlight-card--${tone}`} aria-label={title}>
      <h3><span className="highlight-swatch" aria-hidden="true" />{title}</h3>
      <p>{detail}</p>
      {ranked.length === 0 ? <p className="highlight-empty">No published comparison available.</p> : (
        <ol className="highlight-chart" aria-label={`${title} — top five`}>
          {ranked.map((row) => (
            <li key={row.key}>
              <div className="highlight-chart__plot">
                <span className="highlight-chart__value" style={{ bottom: `${row.value / ceiling * 82}%` }}>{integer.format(row.value)}</span>
                <span className="highlight-chart__bar" style={{ height: `${row.value / ceiling * 82}%` }} aria-hidden="true" />
              </div>
              <span className="highlight-chart__label">{row.label}</span>
            </li>
          ))}
        </ol>
      )}
    </article>
  );
}

export function OverviewHighlights({ data }: { data: PublicDashboardData }) {
  const series = new Map<string, number>();
  // The catalog array may be a preview of the total catalog. Label this chart
  // as the displayed entries, not the full catalog or opening evidence.
  for (const set of data.catalog.sets) {
    const name = set.series ?? "Unspecified";
    series.set(name, (series.get(name) ?? 0) + 1);
  }
  return (
    <section className="overview-highlights" aria-labelledby="highlights-title">
      <h2 id="highlights-title" className="section-label">Highlights</h2>
      <div className="highlight-grid">
        <HighlightChart title="Observed packs" detail="Top country / product-market buckets · Packs" tone="violet"
          rows={data.regions.map((region) => ({ key: region.slug, label: region.name, value: region.packsObserved }))} />
        <HighlightChart title="Complete openings" detail="Top country / product-market buckets · Openings" tone="yellow"
          rows={data.regions.map((region) => ({ key: region.slug, label: region.name, value: region.openings }))} />
        <HighlightChart title="Catalog sets" detail={`Series in the ${integer.format(data.catalog.sets.length)} displayed catalog entries · Metadata only`} tone="orange"
          rows={[...series].map(([name, value]) => ({ key: name, label: name, value }))} />
      </div>
    </section>
  );
}
