"use client";

import React, { useState } from "react";
import type { PublicSource } from "@/data/types";
import { formatCompactNumber, formatDateTime, formatProbability } from "@/lib/format";
import { DefinitionList } from "@/components/ui/dashboard-ui";

function sourceDetails(source: PublicSource) {
  const details = [
    { term: "Kind", value: source.kind },
    { term: "Access", value: source.access },
    { term: "Status", value: source.status },
    { term: "Last collected", value: formatDateTime(source.lastCollectedAt) },
  ];
  const coverage = source.kind === "community" && source.access === "public"
    ? source.coverage
    : undefined;
  if (coverage !== undefined) {
    details.push(
      { term: "Coverage", value: "Reviewed opening-sample facts" },
      { term: "Observed packs", value: formatCompactNumber(coverage.packsObserved) },
      { term: "Attributed coverage buckets", value: formatCompactNumber(coverage.countriesObserved) },
      { term: "Complete openings", value: formatCompactNumber(coverage.completeOpenings) },
    );
    if (coverage.observedRate === undefined) {
      details.push({ term: "Rate sample", value: "No exact normalized numerator" });
    } else {
      details.push(
        { term: "Qualifying hits / rate packs", value: `${formatCompactNumber(coverage.qualifyingHitPacks!)} / ${formatCompactNumber(coverage.ratePacksObserved!)}` },
        { term: "Observed sample rate", value: formatProbability(coverage.observedRate) },
      );
    }
  }
  return details;
}


export function SourceRegistry({ sources }: { sources: readonly PublicSource[] }) {
  const [query, setQuery] = useState("");
  const [kind, setKind] = useState("");
  const [status, setStatus] = useState("");
  const kinds = [...new Set(sources.map((source) => source.kind))].sort();
  const statuses = [...new Set(sources.map((source) => source.status))].sort();
  const search = query.trim().toLocaleLowerCase("en-AU");
  const filtered = sources.filter((source) =>
    (!kind || source.kind === kind) && (!status || source.status === status) &&
    (!search || `${source.name} ${source.note}`.toLocaleLowerCase("en-AU").includes(search)),
  );
  const clear = () => { setQuery(""); setKind(""); setStatus(""); };

  return (
    <div className="source-registry">
      <form className="filter-bar" role="search" aria-label="Filter public sources" onSubmit={(event) => event.preventDefault()}>
        <label><span>Search sources</span><input type="search" value={query} onChange={(event) => setQuery(event.target.value)} placeholder="Source name or description" /></label>
        <label><span>Source type</span><select value={kind} onChange={(event) => setKind(event.target.value)}><option value="">All types</option>{kinds.map((value) => <option key={value} value={value}>{value}</option>)}</select></label>
        <label><span>Availability</span><select value={status} onChange={(event) => setStatus(event.target.value)}><option value="">All statuses</option>{statuses.map((value) => <option key={value} value={value}>{value}</option>)}</select></label>
        {query || kind || status ? <button className="button button--secondary" type="button" onClick={clear}>Clear</button> : null}
      </form>
      <p className="results-line" role="status">{filtered.length} of {sources.length} public sources · expand a source for evidence and collection details</p>
      <ul className="source-list" aria-label="Registered public sources">
        {filtered.map((source) => (
          <li key={source.id}>
            <details className="source-row">
              <summary>
                <span className={`status-dot status-dot--${source.status}`} aria-hidden="true" />
                <span className="source-row__name">{source.name}<small>{source.kind} · {source.access}</small></span>
                <span className="status-label">{source.status}</span>
              </summary>
              <div className="source-row__body">
                <DefinitionList items={sourceDetails(source)} />
                <p>{source.note}</p>
                <a className="external-link" href={source.url} target="_blank" rel="noopener noreferrer">Source reference ↗<span className="sr-only"> (opens in a new tab)</span></a>
              </div>
            </details>
          </li>
        ))}
      </ul>
      {filtered.length === 0 ? <p className="empty-cell">{sources.length === 0 ? "No public source status is available." : "No sources match these filters. Clear the filters to see all sources."}</p> : null}
    </div>
  );
}
