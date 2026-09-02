import React from "react";

import type {
  PublicSocialActivityPulse,
  PublicSource,
  SocialPulseFreshness,
} from "@/data/types";
import { formatCompactNumber, formatDateTime } from "@/lib/format";
import { Panel, SectionHeading } from "@/components/ui/dashboard-ui";

const DISCOVERY_SOURCE_CONTRACTS = {
  youtube: { kind: "video", access: "api-key" },
  youtube_discovery: { kind: "video", access: "api-key" },
  bluesky_jetstream: { kind: "social", access: "public" },
  nostr_multi_relay: { kind: "social", access: "public" },
  mastodon_public_hashtag: { kind: "social", access: "public" },
} as const satisfies Record<string, Pick<PublicSource, "kind" | "access">>;

const freshnessLabel: Record<SocialPulseFreshness, string> = {
  fresh: "Fresh",
  delayed: "Delayed",
  attention: "Needs attention",
  paused: "Paused",
};

export function selectDiscoverySources(sources: readonly PublicSource[]): PublicSource[] {
  return sources.filter((source) => {
    const contract = DISCOVERY_SOURCE_CONTRACTS[
      source.id as keyof typeof DISCOVERY_SOURCE_CONTRACTS
    ];
    return contract?.kind === source.kind && contract.access === source.access;
  });
}

export function LiveDiscoveryPulse({
  pulse,
  sources,
}: {
  pulse?: PublicSocialActivityPulse;
  sources: readonly PublicSource[];
}) {
  const discoverySources = selectDiscoverySources(sources);

  return (
    <section className="dashboard-section discovery-pulse" aria-labelledby="discovery-pulse-title">
      <SectionHeading
        id="discovery-pulse-title"
        title="Live discovery pulse"
        detail="Public social activity in the last 24 hours is shown separately from source health and opening evidence. Activity here does not imply geography, a hit rate, or a pack denominator."
      />
      {!pulse ? (
        <Panel>
          <p className="empty-cell">No public social activity pulse is available.</p>
        </Panel>
      ) : (
        <>
          <div
            className="discovery-pulse__notice"
            role="group"
            aria-label="Social activity scope"
          >
            <span className="eligibility eligibility--activity">Activity only</span>
            <span className="eligibility eligibility--activity">Non-evidence</span>
            <span className="discovery-pulse__window">
              Window: {formatDateTime(pulse.window.start)} – {formatDateTime(pulse.window.end)}
            </span>
          </div>
          <div className="discovery-pulse__grid">
            {pulse.sources.map((source) => (
              <Panel className="discovery-pulse__card" key={source.id}>
                <div className="discovery-pulse__source-heading">
                  <span className={`status-dot status-dot--${source.status}`} aria-hidden="true" />
                  <div>
                    <h3>{source.name}</h3>
                    <span className="discovery-pulse__freshness">{freshnessLabel[source.freshness]}</span>
                  </div>
                </div>
                <dl className="discovery-pulse__metrics">
                  <div>
                    <dt>New candidates (24h)</dt>
                    <dd>{formatCompactNumber(source.newCandidates24h)}</dd>
                  </div>
                  <div>
                    <dt>Retained candidates</dt>
                    <dd>{formatCompactNumber(source.retainedCandidates)}</dd>
                  </div>
                  <div>
                    <dt>Last collected</dt>
                    <dd>{formatDateTime(source.lastCollectedAt)}</dd>
                  </div>
                </dl>
                <p className="discovery-pulse__caveat">Activity only · not evidence for packs, country, or rate.</p>
              </Panel>
            ))}
          </div>
        </>
      )}

      <section className="discovery-pulse__provenance" aria-labelledby="discovery-source-health-title">
        <h3 id="discovery-source-health-title">Public discovery source health</h3>
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
    </section>
  );
}
