import React, { type ReactNode } from "react";
import type { Route } from "next";
import Link from "next/link";

import type {
  BatchMetric,
  ObservedMetric,
  PublicDashboardData,
  RegionMetric,
  RetailerMetric,
  SetMetric,
} from "@/data/types";
import { formatCompactNumber, formatDate, formatDateTime, formatProbability } from "@/lib/format";
import {
  DataModeNotice,
  DefinitionList,
  EmptyTableRow,
  MetricDisclaimer,
  ObservationStats,
  PageIntro,
  Panel,
  SectionHeading,
  SignalBadge,
  TableFrame,
} from "@/components/ui/dashboard-ui";
import type { SetSort } from "@/app/_lib/sets-query";

interface MetricRow {
  key: string;
  href: Route;
  name: string;
  meta: string;
  metric: ObservedMetric;
}

function MetricTable({ rows, label, emptyMessage }: { rows: readonly MetricRow[]; label: string; emptyMessage: string }) {
  return (
    <Panel>
      <TableFrame label={label}>
        <table>
          <thead><tr><th>Name</th><th>Packs</th><th>Openings</th><th>Observed rate</th><th>Signal</th></tr></thead>
          <tbody>
            {rows.length === 0 ? <EmptyTableRow columns={5} message={emptyMessage} /> : rows.map((row) => (
              <tr key={row.key}>
                <td><Link className="entity-link" href={row.href}><strong>{row.name}</strong><small>{row.meta}</small></Link></td>
                <td>{formatCompactNumber(row.metric.packsObserved)}</td>
                <td>{formatCompactNumber(row.metric.openings)}</td>
                <td>{formatProbability(row.metric.hitRate)}</td>
                <td><SignalBadge metric={row.metric} /></td>
              </tr>
            ))}
          </tbody>
        </table>
      </TableFrame>
    </Panel>
  );
}

function PublicPage({ children, synthetic, generatedAt }: { children: ReactNode; synthetic: boolean; generatedAt: string }) {
  return <div className="page-shell"><DataModeNotice synthetic={synthetic} generatedAt={generatedAt} />{children}</div>;
}

export function SetsView({ data, sets, query, sort, synthetic }: { data: PublicDashboardData; sets: readonly SetMetric[]; query: string; sort: SetSort; synthetic: boolean }) {
  const rows = sets.map((set) => ({
    key: set.slug,
    href: `/sets/${set.slug}` as Route,
    name: set.name,
    meta: `${set.series} · released ${formatDate(set.releaseDate)}`,
    metric: set,
  }));
  return (
    <PublicPage synthetic={synthetic} generatedAt={data.generatedAt}>
      <PageIntro eyebrow="Observed sets" title="Set aggregates" description="Compare published sample sizes, observed rates, intervals and exploratory signal states across tracked sets." />
      <form className="filter-bar" action="/sets" method="get" role="search">
        <label><span>Search sets</span><input type="search" name="q" defaultValue={query} placeholder="Name or series" /></label>
        <label><span>Sort</span><select name="sort" defaultValue={sort}><option value="packs">Most observed</option><option value="rate">Observed rate</option><option value="release">Newest release</option><option value="name">Name</option></select></label>
        <button className="button" type="submit">Apply</button>
        {(query || sort !== "packs") ? <Link className="button button--secondary" href="/sets">Clear</Link> : null}
      </form>
      <div className="results-line" aria-live="polite"><strong>{sets.length}</strong> of {data.sets.length} published sets</div>
      <MetricTable rows={rows} label="Published set aggregates" emptyMessage="No published sets match this search." />
      <MetricDisclaimer />
    </PublicPage>
  );
}

export function SetDetailView({ data, set, synthetic }: { data: PublicDashboardData; set: SetMetric; synthetic: boolean }) {
  const relatedBatches = data.batches.filter((batch) => batch.setSlug === set.slug);
  const relatedActivity = data.recentActivity.filter((item) => item.setName === set.name);
  return (
    <PublicPage synthetic={synthetic} generatedAt={data.generatedAt}>
      <PageIntro eyebrow={`${set.series} · set observation`} title={set.name} description="Published aggregate for validated, complete observations in the current snapshot.">
        <div className="intro-meta"><span>Released {formatDate(set.releaseDate)}</span><span>Updated {formatDateTime(set.updatedAt)}</span></div>
      </PageIntro>
      <ObservationStats metric={set} />
      <div className="detail-grid">
        <Panel><h2>Interpretation</h2><p>{set.sampleNote}</p><p>{set.signal}</p><SignalBadge metric={set} /></Panel>
        <Panel><h2>Scope</h2><DefinitionList items={[{ term: "Series", value: set.series }, { term: "Set slug", value: <code>{set.slug}</code> }, { term: "Denominator", value: "Eligible packs observed" }, { term: "Snapshot", value: formatDateTime(data.generatedAt) }]} /></Panel>
      </div>
      <section className="dashboard-section"><SectionHeading title="Visible batches" detail="Batch labels connected to this set in the aggregate snapshot." /><MetricTable rows={relatedBatches.map((batch) => ({ key: batch.code, href: `/batches/${encodeURIComponent(batch.code)}` as Route, name: batch.code, meta: `${batch.productType} · ${batch.region}`, metric: batch }))} label={`Visible batches for ${set.name}`} emptyMessage="No visible batch aggregates are linked to this set." /></section>
      <section className="dashboard-section"><SectionHeading title="Recent activity" detail="Published activity can include records excluded from rate calculations." /><Panel><ul className="activity-list">{relatedActivity.length === 0 ? <li className="empty-cell">No recent public activity is linked to this set.</li> : relatedActivity.map((item) => <li key={item.id}><time dateTime={item.observedAt}>{formatDateTime(item.observedAt)}</time><span>{item.productType} · {item.packCount} packs · {item.region}</span><span>{item.statisticsEligible ? `Tier ${item.evidenceTier}` : "Activity only"}</span></li>)}</ul></Panel></section>
      <MetricDisclaimer />
    </PublicPage>
  );
}

export function RegionsView({ data, synthetic }: { data: PublicDashboardData; synthetic: boolean }) {
  const rows = data.regions.map((region) => ({ key: region.slug, href: `/regions/${region.slug}` as Route, name: region.name, meta: region.coverage, metric: region }));
  return (
    <PublicPage synthetic={synthetic} generatedAt={data.generatedAt}>
      <PageIntro eyebrow="Legacy Australia v1 detail" title="Regional observations" description="These legacy regional aggregates retain the reviewed Australia-only v1 boundary. The global country-level atlas is published on the dashboard." />
      <div className="coverage-grid coverage-grid--list">{data.regions.map((region, index) => <Link className={`coverage-cell coverage-cell--${(index % 4) + 1}`} href={`/regions/${region.slug}` as Route} key={region.slug}><span className="coverage-cell__index">{region.countryCode}.{String(index + 1).padStart(2, "0")}</span><strong>{region.name}</strong><span>{region.coverage}</span><SignalBadge metric={region} /></Link>)}</div>
      <MetricTable rows={rows} label="Regional aggregate comparison" emptyMessage="No region aggregates are published in this snapshot." />
      <MetricDisclaimer />
    </PublicPage>
  );
}

export function RegionDetailView({ data, region, synthetic }: { data: PublicDashboardData; region: RegionMetric; synthetic: boolean }) {
  const retailers = data.retailers.filter((retailer) => retailer.region === region.name);
  const batches = data.batches.filter((batch) => batch.region === region.name);
  return (
    <PublicPage synthetic={synthetic} generatedAt={data.generatedAt}>
      <PageIntro eyebrow={`${region.countryCode} · regional observation`} title={region.name} description={region.coverage}><div className="intro-meta"><span>Updated {formatDateTime(region.updatedAt)}</span></div></PageIntro>
      <ObservationStats metric={region} />
      <div className="detail-grid"><Panel><h2>Coverage note</h2><p>{region.sampleNote}</p><p>Regional activity reflects the sources collected, not the underlying distribution of all purchases.</p></Panel><Panel><h2>Published scope</h2><DefinitionList items={[{ term: "Country", value: region.countryCode }, { term: "Region key", value: <code>{region.slug}</code> }, { term: "Retailer aggregates", value: retailers.length }, { term: "Visible batches", value: batches.length }]} /></Panel></div>
      <section className="dashboard-section"><SectionHeading title="Retailer observations" detail="Aggregate retailer labels within this regional snapshot." /><MetricTable rows={retailers.map((retailer) => ({ key: retailer.slug, href: `/retailers/${retailer.slug}` as Route, name: retailer.name, meta: retailer.channel, metric: retailer }))} label={`Retailer observations in ${region.name}`} emptyMessage="No retailer aggregates are linked to this region." /></section>
      <section className="dashboard-section"><SectionHeading title="Visible batch observations" /><MetricTable rows={batches.map((batch) => ({ key: batch.code, href: `/batches/${encodeURIComponent(batch.code)}` as Route, name: batch.code, meta: `${batch.setName} · ${batch.productType}`, metric: batch }))} label={`Batch observations in ${region.name}`} emptyMessage="No visible batches are linked to this region." /></section>
      <MetricDisclaimer />
    </PublicPage>
  );
}

export function RetailersView({ data, synthetic }: { data: PublicDashboardData; synthetic: boolean }) {
  const rows = data.retailers.map((retailer) => ({ key: retailer.slug, href: `/retailers/${retailer.slug}` as Route, name: retailer.name, meta: `${retailer.region} · ${retailer.channel}`, metric: retailer }));
  return (
    <PublicPage synthetic={synthetic} generatedAt={data.generatedAt}>
      <PageIntro eyebrow="Attributed activity" title="Retailer observations" description="Published retailer groupings show sample coverage only. They do not rank stores or establish causes." />
      <MetricTable rows={rows} label="Retailer aggregate comparison" emptyMessage="No retailer aggregates are published in this snapshot." />
      <MetricDisclaimer />
    </PublicPage>
  );
}

export function RetailerDetailView({ data, retailer, synthetic }: { data: PublicDashboardData; retailer: RetailerMetric; synthetic: boolean }) {
  const activity = data.recentActivity.filter((item) => item.retailer === retailer.name);
  return (
    <PublicPage synthetic={synthetic} generatedAt={data.generatedAt}>
      <PageIntro eyebrow={`${retailer.channel} · retailer observation`} title={retailer.name} description={`Attributed observations for ${retailer.region}.`}><div className="intro-meta"><span>Updated {formatDateTime(retailer.updatedAt)}</span></div></PageIntro>
      <ObservationStats metric={retailer} />
      <div className="detail-grid"><Panel><h2>Interpretation</h2><p>{retailer.sampleNote}</p><p>Retailer attribution can be incomplete or self-reported; observed differences do not establish retailer influence.</p></Panel><Panel><h2>Published scope</h2><DefinitionList items={[{ term: "Region", value: retailer.region }, { term: "Channel", value: retailer.channel }, { term: "Retailer key", value: <code>{retailer.slug}</code> }, { term: "Recent activities", value: activity.length }]} /></Panel></div>
      <section className="dashboard-section"><SectionHeading title="Recent attributed activity" detail="Only public-safe aggregate context is shown." /><Panel><ul className="activity-list">{activity.length === 0 ? <li className="empty-cell">No recent public activity is attributed to this retailer.</li> : activity.map((item) => <li key={item.id}><time dateTime={item.observedAt}>{formatDateTime(item.observedAt)}</time><span>{item.setName} · {item.productType} · {item.packCount} packs</span><span>{item.statisticsEligible ? `Tier ${item.evidenceTier}` : "Activity only"}</span></li>)}</ul></Panel></section>
      <MetricDisclaimer />
    </PublicPage>
  );
}

export function BatchesView({ data, synthetic }: { data: PublicDashboardData; synthetic: boolean }) {
  const rows = data.batches.map((batch) => ({ key: batch.code, href: `/batches/${encodeURIComponent(batch.code)}` as Route, name: batch.code, meta: `${batch.setName} · ${batch.productType} · ${batch.region}`, metric: batch }));
  return (
    <PublicPage synthetic={synthetic} generatedAt={data.generatedAt}>
      <PageIntro eyebrow="Visible labels" title="Batch observations" description="Visible batch or lot labels connect observations for exploratory aggregation; labels may be incomplete or inconsistently reported." />
      <MetricTable rows={rows} label="Visible batch aggregate comparison" emptyMessage="No batch aggregates are published in this snapshot." />
      <MetricDisclaimer batch />
    </PublicPage>
  );
}

export function BatchDetailView({ data, batch, synthetic }: { data: PublicDashboardData; batch: BatchMetric; synthetic: boolean }) {
  const set = data.sets.find((candidate) => candidate.slug === batch.setSlug);
  return (
    <PublicPage synthetic={synthetic} generatedAt={data.generatedAt}>
      <MetricDisclaimer batch />
      <PageIntro eyebrow={`${batch.productType} · visible batch observation`} title={batch.code} description={`${batch.setName} observations attributed to ${batch.region}.`}><div className="intro-meta"><span>{formatDate(batch.firstObserved)} to {formatDate(batch.lastObserved)}</span><span>Updated {formatDateTime(batch.updatedAt)}</span></div></PageIntro>
      <ObservationStats metric={batch} />
      <div className="detail-grid"><Panel><h2>Interpretation</h2><p>{batch.sampleNote}</p><p>Batch labels are observational groupings and may not correspond to a single production run.</p></Panel><Panel><h2>Published scope</h2><DefinitionList items={[{ term: "Set", value: set ? <Link href={`/sets/${set.slug}` as Route}>{batch.setName}</Link> : batch.setName }, { term: "Product", value: batch.productType }, { term: "Region", value: batch.region }, { term: "Window", value: `${formatDate(batch.firstObserved)} to ${formatDate(batch.lastObserved)}` }]} /></Panel></div>
    </PublicPage>
  );
}

export function MethodologyView({ data, synthetic }: { data: PublicDashboardData; synthetic: boolean }) {
  return (
    <PublicPage synthetic={synthetic} generatedAt={data.generatedAt}>
      <PageIntro eyebrow={`Methodology ${data.summary.methodologyVersion}`} title="How observations become aggregates" description="A conservative, versioned pipeline separates public activity sightings from complete observations eligible for statistical summaries." />
      <div className="prose-grid">
        <Panel><span className="eyebrow">01 · Source policy</span><h2>Bounded source types</h2><p>Every adapter starts with an explicit source policy: exact domain and route, permitted fields, terms and robots review, access mode, limits, retention, owner and kill switch. Unknown or disabled sources fail closed.</p></Panel>
        <Panel><span className="eyebrow">02 · AI review</span><h2>Extract, validate, resolve</h2><p>An AI Extractor produces strict candidate facts. An independent AI Validator evaluates the source evidence and extraction. One bounded escalation may resolve agreement; malformed, conflicting or low-confidence results are rejected.</p></Panel>
        <Panel><span className="eyebrow">03 · Identity</span><h2>Dedup and cross-post checks</h2><p>Canonical platform identifiers, URLs, content fingerprints and normalized opening identities detect duplicates, reposts and cross-posts. Suspected duplicates are linked and excluded from denominators.</p></Panel>
        <Panel><span className="eyebrow">04 · Completeness</span><h2>Complete opening required</h2><p>A complete opening needs a known positive pack count, catalog-consistent set and product, accepted validation and no duplicate flag. Ambiguous or partial openings are excluded rather than imputed.</p></Panel>
        <Panel><span className="eyebrow">05 · Evidence</span><h2>Tiers and activity-only records</h2><p>Evidence tiers A and B can become statistics eligible after deterministic validation. Tier C and D records remain activity-only when the denominator or evidence is incomplete; an AI statement cannot promote unsupported evidence.</p></Panel>
        <Panel><span className="eyebrow">06 · Eligibility</span><h2>Statistics eligibility</h2><p>Eligibility requires a complete, nonduplicate, accepted tier A/B opening with a known set, positive pack count and explicit <code>statistics_eligible=true</code>. Activity-only records never contribute to the rate denominator.</p></Panel>
        <Panel><span className="eyebrow">07 · Observed rate</span><h2>Count packs, not posts</h2><p>The observed rate is accepted observed hits divided by eligible packs observed. Posts, videos, products, boxes and reported hits are not used as the denominator.</p></Panel>
        <Panel><span className="eyebrow">08 · Baseline</span><h2>Versioned fallback</h2><p>A set/product/rarity baseline is preferred. Baseline fallback moves to a documented broader level only when the specific baseline is unavailable, and its identity is retained with the aggregate.</p></Panel>
        <Panel><span className="eyebrow">09 · Estimation</span><h2>Empirical Bayes interval</h2><p>A binomial/Beta empirical Bayes estimate stabilizes small samples against the versioned baseline. Published summaries include the center and a 90% credible interval alongside the observed sample size.</p></Panel>
        <Panel><span className="eyebrow">10 · Thresholds</span><h2>Minimum samples and sources</h2><p>Rate display and comparative signals both require minimum source diversity. Rate display begins at 30 eligible packs from at least three independent sources. Comparative signals require at least 200 packs, practical uplift and configured posterior probability; below-threshold values are withheld.</p></Panel>
        <Panel><span className="eyebrow">11 · Bias</span><h2>Interpret context carefully</h2><p>Social selection bias means posted openings are not a random sample. Regional correlation does not establish causation. Retailer inventory or attribution is not pull evidence and cannot establish retailer influence.</p></Panel>
        <Panel><span className="eyebrow">12 · Reproducibility</span><h2>Version and update frequency</h2><p>Methodology version <strong>{data.summary.methodologyVersion}</strong> defines this snapshot. Aggregate update frequency follows the scheduled rollup after accepted observations; each page shows its generated and updated timestamps rather than implying continuous coverage.</p></Panel>
      </div>
      <Panel className="policy-panel"><h2>Evidence tier reference</h2><TableFrame label="Evidence tier definitions"><table><thead><tr><th>Tier</th><th>Use</th><th>Statistical default</th></tr></thead><tbody><tr><td>A</td><td>Directly countable complete opening with strong catalog match.</td><td>Eligible after validation</td></tr><tr><td>B</td><td>Complete count supported by consistent structured context.</td><td>Eligible after validation</td></tr><tr><td>C</td><td>Useful sighting with incomplete denominator or weaker evidence.</td><td>Activity only</td></tr><tr><td>D</td><td>Mention or discovery metadata.</td><td>Activity only</td></tr></tbody></table></TableFrame></Panel>
      <MetricDisclaimer />
    </PublicPage>
  );
}

export function SourcesView({ data, synthetic }: { data: PublicDashboardData; synthetic: boolean }) {
  const sourceTypes = [
    ["Official APIs", "Catalog and discovery metadata under published provider terms."],
    ["RSS", "Bounded feed discovery when the policy explicitly enables the feed."],
    ["Sitemaps", "Discovery URLs only, within reviewed route and page limits."],
    ["Public JSON", "Documented or policy-approved public structured endpoints."],
    ["Policy-approved public pages", "Static or dynamic metadata fields explicitly permitted by the source registry."],
    ["Authenticated OpenCLI adapters", "Owner-authorized accounts for permitted metadata; login never expands collection rights."],
    ["Admin CSV/JSONL imports", "Schema-validated, synthetic or owner-authorized bounded imports with audit context."],
    ["Authorized media", "Metadata and bounded evidence from media the operator is authorized to process."],
  ] as const;
  return (
    <PublicPage synthetic={synthetic} generatedAt={data.generatedAt}>
      <PageIntro eyebrow="Public provenance" title="Sources and collection boundaries" description="Only public-safe source classes and operational notes are shown; private evidence, accounts and payloads stay outside the public dashboard." />
      <Panel className="policy-panel"><h2>Collection policy</h2><p>Official sources and bounded structured metadata are preferred. Every source needs an exact, versioned policy covering routes, fields, terms, robots behavior, limits, retention, owner, review date and kill switch. Unknown domains and disabled routes fail closed.</p><div className="source-type-grid">{sourceTypes.map(([name, detail]) => <div key={name}><h3>{name}</h3><p>{detail}</p></div>)}</div></Panel>
      <Panel className="policy-panel policy-panel--warning"><h2>Explicitly outside scope</h2><ul className="policy-list"><li>No login or CAPTCHA bypass; an access challenge stops automated collection.</li><li>No proxy pools, stealth rotation, credential sharing or collection after access denial.</li><li>No long-term full third-party video retention, full-content rehosting or third-party content archive.</li><li>No private-message collection, hidden account creation or automated purchasing.</li></ul></Panel>
      <section className="dashboard-section"><SectionHeading title="Registered public source classes" detail="Status reflects the aggregate snapshot, not a promise of future availability." /><div className="card-grid">{data.sources.length === 0 ? <Panel><p className="empty-cell">No public source status is available.</p></Panel> : data.sources.map((source) => <Panel key={source.id}><div className="card-heading"><span className={`status-dot status-dot--${source.status}`} /><h3>{source.name}</h3></div><DefinitionList items={[{ term: "Kind", value: source.kind }, { term: "Access", value: source.access }, { term: "Status", value: source.status }, { term: "Last collected", value: formatDateTime(source.lastCollectedAt) }]} /><p>{source.note}</p><a className="external-link" href={source.url} target="_blank" rel="noopener noreferrer">Source reference ↗<span className="sr-only"> (opens in a new tab)</span></a></Panel>)}</div></section>
    </PublicPage>
  );
}

export function StatusView({ data, synthetic }: { data: PublicDashboardData; synthetic: boolean }) {
  const degraded = data.services.some((service) => service.status !== "operational");
  return (
    <PublicPage synthetic={synthetic} generatedAt={data.generatedAt}>
      <PageIntro eyebrow="Public status" title={degraded ? "Some services need attention" : "All published services operational"} description="Public, aggregate-level status only. Sensitive infrastructure details are intentionally omitted." />
      <div className="status-list">{data.services.length === 0 ? <Panel><p className="empty-cell">No public service checks are available.</p></Panel> : data.services.map((service) => <Panel key={service.id}><div className="card-heading"><span className={`status-dot status-dot--${service.status}`} /><h2>{service.name}</h2><span className="status-label">{service.status}</span></div><p>{service.detail}</p><time dateTime={service.checkedAt}>Checked {formatDateTime(service.checkedAt)}</time></Panel>)}</div>
      <Panel className="policy-panel"><h2>Snapshot freshness</h2><p>Dashboard snapshot generated {formatDateTime(data.generatedAt)}. Status entries are bounded public summaries and may lag underlying checks.</p><Link className="text-link" href="/sources">Review source availability →</Link></Panel>
    </PublicPage>
  );
}
