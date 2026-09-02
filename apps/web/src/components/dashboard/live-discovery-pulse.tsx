import React from "react";

import type { PublicSocialActivityPulse, SocialPulseFreshness } from "@/data/types";
import { formatCompactNumber, formatDateTime } from "@/lib/format";
import { Panel, SectionHeading } from "@/components/ui/dashboard-ui";

const freshnessLabel: Record<SocialPulseFreshness, string> = {
  fresh: "Fresh",
  delayed: "Delayed",
  attention: "Needs attention",
  paused: "Paused",
};

export function LiveDiscoveryPulse({ pulse }: { pulse?: PublicSocialActivityPulse }) {
  return (
    <section className="dashboard-section discovery-pulse" aria-labelledby="discovery-pulse-title">
      <SectionHeading
        id="discovery-pulse-title"
        title="Live discovery pulse"
        detail="Public social activity detected in the last 24 hours, split by platform."
      />
      {!pulse ? (
        <Panel>
          <p className="empty-cell">No public social activity pulse is available.</p>
        </Panel>
      ) : (
        <>
          <div className="discovery-pulse__notice" aria-label="Social activity scope">
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
    </section>
  );
}
