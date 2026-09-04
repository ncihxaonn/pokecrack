import Link from "next/link";

import type { PublicSource, PublicSourceCoverage } from "@/data/types";
import { formatCompactNumber, formatDateTime } from "@/lib/format";
import { SectionHeading } from "@/components/ui/dashboard-ui";

type ReviewedEvidenceSource = PublicSource & {
  readonly coverage: PublicSourceCoverage;
};

function hasReviewedCoverage(source: PublicSource): source is ReviewedEvidenceSource {
  return source.kind === "community" && source.access === "public" && source.coverage !== undefined;
}

function plural(value: number, singular: string, pluralForm = `${singular}s`): string {
  return `${formatCompactNumber(value)} ${value === 1 ? singular : pluralForm}`;
}

export function ReviewedEvidenceSources({ sources }: { sources: readonly PublicSource[] }) {
  const reviewedSources = sources.filter(hasReviewedCoverage);

  if (reviewedSources.length === 0) return null;

  return (
    <section className="dashboard-section reviewed-evidence" aria-labelledby="reviewed-evidence-title">
      <SectionHeading
        id="reviewed-evidence-title"
        title="Reviewed evidence sources"
        detail="Verified opening-sample coverage only — not a hit rate. Coverage-bucket attribution follows each reviewed source's declared basis and is not necessarily an opening location. Social discovery is excluded from these counts."
        action={<Link className="text-link" href="/sources">Source boundaries →</Link>}
      />
      <ul className="reviewed-source-rail" aria-label="Reviewed evidence source coverage">
        {reviewedSources.map((source) => (
          <li key={source.id}>
            <div className="reviewed-source-rail__identity">
              <a href={source.url} target="_blank" rel="noopener noreferrer">
                <strong>{source.name}</strong>
                <span>Source reference ↗<span className="sr-only"> (opens in a new tab)</span></span>
              </a>
              <span className="reviewed-source-rail__status">
                <span className={`status-dot status-dot--${source.status}`} aria-hidden="true" />
                {source.status}
              </span>
            </div>
            <dl className="reviewed-source-rail__metrics">
              <div>
                <dt>Observed packs</dt>
                <dd>{plural(source.coverage.packsObserved, "pack")}</dd>
              </div>
              <div>
                <dt>Attributed coverage buckets</dt>
                <dd>{plural(source.coverage.countriesObserved, "bucket", "buckets")}</dd>
              </div>
              <div>
                <dt>Complete openings</dt>
                <dd>{plural(source.coverage.completeOpenings, "opening")}</dd>
              </div>
              <div>
                <dt>Last collected</dt>
                <dd>
                  {source.lastCollectedAt === null
                    ? "Never"
                    : <time dateTime={source.lastCollectedAt}>{formatDateTime(source.lastCollectedAt)}</time>}
                </dd>
              </div>
            </dl>
          </li>
        ))}
      </ul>
    </section>
  );
}
