import React from "react";

import type { PublicSource } from "@/data/types";
import { formatDateTime } from "@/lib/format";
import { SectionHeading } from "@/components/ui/dashboard-ui";

const KNOWN_YOUTUBE_SOURCE_IDS = new Set(["youtube", "youtube_discovery"]);
const KNOWN_YOUTUBE_SOURCE_NAMES = new Set([
  "YouTube Data API",
  "YouTube global discovery",
]);

function isKnownYouTubeSource(source: PublicSource): boolean {
  return KNOWN_YOUTUBE_SOURCE_IDS.has(source.id) || KNOWN_YOUTUBE_SOURCE_NAMES.has(source.name);
}

export function selectDiscoverySources(sources: readonly PublicSource[]): PublicSource[] {
  return sources.filter((source) =>
    (source.kind === "social" && source.access === "public") || isKnownYouTubeSource(source),
  );
}

export function LiveDiscoveryPulse({ sources }: { sources: readonly PublicSource[] }) {
  const discoverySources = selectDiscoverySources(sources);

  return (
    <section className="dashboard-section discovery-pulse" aria-labelledby="discovery-pulse-title">
      <SectionHeading
        id="discovery-pulse-title"
        title="Live discovery pulse"
        detail="Public source health is shown separately from opening evidence. Activity here does not imply geography, a hit rate, or a pack denominator."
      />
      {discoverySources.length === 0 ? (
        <p className="discovery-pulse__empty">No public discovery source status is available.</p>
      ) : (
        <ul className="discovery-pulse__list">
          {discoverySources.map((source) => (
            <li className="discovery-pulse__item" key={source.id}>
              <div className="discovery-pulse__heading">
                <a
                  className="external-link discovery-pulse__link"
                  href={source.url}
                  target="_blank"
                  rel="noopener noreferrer"
                >
                  {source.name}
                  <span className="sr-only"> (opens in a new tab)</span>
                </a>
                <span
                  className={`discovery-pulse__status discovery-pulse__status--${source.status}`}
                  aria-label={`${source.name} status: ${source.status}`}
                >
                  {source.status}
                </span>
              </div>
              <dl className="discovery-pulse__meta">
                <div>
                  <dt>Last collected</dt>
                  <dd>
                    <time dateTime={source.lastCollectedAt ?? undefined}>
                      {formatDateTime(source.lastCollectedAt)}
                    </time>
                  </dd>
                </div>
              </dl>
              <p className="discovery-pulse__note">{source.note}</p>
            </li>
          ))}
        </ul>
      )}
    </section>
  );
}
