"use client";

import React, { useState } from "react";
import type { Route } from "next";
import Link from "next/link";

import type { RegionMetric } from "@/data/types";
import { formatCompactNumber, formatProbability } from "@/lib/format";
import { getSignalPresentation } from "@/lib/signals";

type CoverageMetric = "packs" | "openings" | "rate" | "quality";

const options: readonly { value: CoverageMetric; label: string }[] = [
  { value: "packs", label: "Observed Packs" },
  { value: "openings", label: "Complete Openings" },
  { value: "rate", label: "Observed SIR Rate" },
  { value: "quality", label: "Sample Quality" },
];

function displayValue(region: RegionMetric, metric: CoverageMetric): string {
  if (metric === "packs") return `${formatCompactNumber(region.packsObserved)} packs`;
  if (metric === "openings") return `${formatCompactNumber(region.openings)} openings`;
  if (metric === "rate") return formatProbability(region.hitRate);
  return getSignalPresentation(region.state).label;
}

export function CoverageGrid({ regions }: { regions: readonly RegionMetric[] }) {
  const [metric, setMetric] = useState<CoverageMetric>("packs");
  return (
    <div>
      <div className="metric-toggle" role="group" aria-label="Australian coverage metric">
        {options.map((option) => <button type="button" key={option.value} aria-pressed={metric === option.value} onClick={() => setMetric(option.value)}>{option.label}</button>)}
      </div>
      <div className="coverage-grid">
        {regions.length === 0 ? <p className="empty-cell">No region aggregates are published in this snapshot.</p> : regions.map((region, index) => (
          <Link className={`coverage-cell coverage-cell--${(index % 4) + 1}`} href={`/regions/${region.slug}` as Route} key={region.slug}>
            <span className="coverage-cell__index">AU.{String(index + 1).padStart(2, "0")}</span>
            <strong>{region.name.replace("Australia · ", "")}</strong>
            <span>{displayValue(region, metric)}</span>
          </Link>
        ))}
      </div>
      <p className="coverage-caveat">This control changes the displayed observation metric. None of these measures represents luck.</p>
    </div>
  );
}
