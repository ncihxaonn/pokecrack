"use client";

import React, { useState } from "react";
import type { CatalogSnapshot } from "@/data/types";
import { formatDate } from "@/lib/format";
import { TableFrame } from "@/components/ui/dashboard-ui";
import styles from "./overview-charts.module.css";

const PAGE_SIZE = 12;

export function OverviewCatalog({ catalog }: { catalog: CatalogSnapshot }) {
  const [query, setQuery] = useState("");
  const [page, setPage] = useState(0);
  const filtered = catalog.sets.filter((set) => `${set.name} ${set.series ?? ""}`.toLocaleLowerCase("en-AU").includes(query.trim().toLocaleLowerCase("en-AU")));
  const lastPage = Math.max(0, Math.ceil(filtered.length / PAGE_SIZE) - 1);
  const current = Math.min(page, lastPage);
  const start = current * PAGE_SIZE;
  const visible = filtered.slice(start, start + PAGE_SIZE);
  const hasSeries = catalog.sets.some((set) => set.series !== null);
  const hasReleaseDates = catalog.sets.some((set) => set.releaseDate !== null);

  return <section className="dashboard-section" aria-labelledby="catalog-title">
    <div className={styles.heading}><div><h2 id="catalog-title">Global set catalog</h2><p>{catalog.setCount.toLocaleString("en-AU")} catalog entries · metadata only, never opening evidence or a pull-rate denominator.</p></div></div>
    <div className={styles.card}>
      <div className={styles.filters}><label><span className="sr-only">Search catalog</span><input type="search" value={query} onChange={(event) => { setQuery(event.target.value); setPage(0); }} placeholder="Search the available sets" /></label></div>
      <TableFrame label="Global TCGdex set catalog">
        <table>
          <thead><tr><th scope="col">Set</th>{hasSeries ? <th scope="col">Series</th> : null}{hasReleaseDates ? <th scope="col">Release</th> : null}<th scope="col">Language</th></tr></thead>
          <tbody>{visible.length === 0 ? <tr><td colSpan={2 + Number(hasSeries) + Number(hasReleaseDates)} className="empty-cell">No catalog entries match this search.</td></tr> : visible.map((set) => <tr key={set.id}>
            <td><strong>{set.name}</strong></td>{hasSeries ? <td>{set.series ?? "—"}</td> : null}{hasReleaseDates ? <td>{set.releaseDate ? formatDate(set.releaseDate) : "—"}</td> : null}<td>{set.language.toUpperCase()}</td>
          </tr>)}</tbody>
        </table>
      </TableFrame>
      <div className={styles.pagination}>
        <p role="status">{filtered.length === 0 ? "0 results" : `${start + 1}–${Math.min(start + PAGE_SIZE, filtered.length)} of ${filtered.length} matching entries`}{catalog.sets.length < catalog.setCount ? ` · ${catalog.sets.length} of ${catalog.setCount} entries available in this snapshot` : ""}</p>
        <div><button type="button" disabled={current === 0} onClick={() => setPage(current - 1)}>Previous</button><button type="button" disabled={current === lastPage} onClick={() => setPage(current + 1)}>Next</button></div>
      </div>
    </div>
  </section>;
}
