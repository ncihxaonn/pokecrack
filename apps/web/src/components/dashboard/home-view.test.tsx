import React from "react";
import { fireEvent, render, screen } from "@testing-library/react";
import { describe, expect, it } from "vitest";

import { BRAND } from "@/config/brand";
import { DEMO_PUBLIC_DATA } from "@/data/demo";
import type { PublicDashboardData, PublicSocialActivityPulse } from "@/data/types";
import { getSignalPresentation } from "@/lib/signals";
import { HomeView } from "./home-view";

describe("HomeView", () => {
  it("renders the required synthetic dashboard sections and observational caveats", () => {
    render(<HomeView data={DEMO_PUBLIC_DATA} synthetic />);

    expect(screen.getByRole("heading", { level: 1, name: "Overview" })).toBeVisible();
    expect(screen.getByText(BRAND.demoNotice)).toBeVisible();
    expect(screen.getByText(BRAND.individualPackDisclaimer)).toBeVisible();
    expect(screen.getByRole("heading", { name: "Worldwide qualifying-hit map" })).toBeVisible();
    expect(screen.queryByRole("heading", { name: "Live discovery pulse" })).not.toBeInTheDocument();
    expect(screen.queryByRole("link", { name: /YouTube Data API/ })).not.toBeInTheDocument();
    expect(screen.queryByRole("link", { name: /Reddit authenticated session/ })).not.toBeInTheDocument();
    expect(screen.queryByRole("link", { name: /X authenticated session/ })).not.toBeInTheDocument();
    expect(screen.getByText(/fixed absolute colour scale/i)).toBeVisible();
    expect(screen.getByRole("heading", { name: "Global set catalog" })).toBeVisible();
    expect(screen.getByText(/never opening evidence or a pull-rate denominator/i)).toBeVisible();
    expect(screen.getByRole("heading", { name: "Trending sets" })).toBeVisible();
    expect(screen.getByRole("heading", { name: "Signal watch" })).toBeVisible();
    expect(screen.getByRole("heading", { name: "Recent observed activity" })).toBeVisible();
    expect(screen.queryByRole("heading", { name: "Methodology at a glance" })).not.toBeInTheDocument();
    expect(screen.queryByRole("link", { name: /methodology|all sources|system status/i })).not.toBeInTheDocument();
    expect(screen.getAllByText(getSignalPresentation("anomaly").label).length).toBeGreaterThan(0);
    expect(screen.getAllByText("4,872").length).toBeGreaterThan(0);

    const mapHeading = screen.getByRole("heading", { name: "Worldwide qualifying-hit map" });
    const trendHeading = screen.getByRole("heading", { name: "Observed trend" });
    expect(mapHeading.compareDocumentPosition(trendHeading) & Node.DOCUMENT_POSITION_FOLLOWING).toBeTruthy();
  });

  it("omits source and operational panels even when reviewed coverage exists", () => {
    const reviewedCoverage = {
      ...DEMO_PUBLIC_DATA,
      sources: [
        ...DEMO_PUBLIC_DATA.sources,
        {
          id: "comicbook_perfect_order_study",
          name: "ComicBook Perfect Order study",
          kind: "community" as const,
          access: "public" as const,
          status: "operational" as const,
          lastCollectedAt: "2026-09-03T01:00:00.000Z",
          url: "https://comicbook.com/example",
          note: "Reviewed opening sample.",
          coverage: {
            packsObserved: 55,
            countriesObserved: 1,
            completeOpenings: 1,
          },
        },
      ],
    } satisfies PublicDashboardData;

    render(<HomeView data={reviewedCoverage} synthetic={false} />);

    const mapHeading = screen.getByRole("heading", { name: "Worldwide qualifying-hit map" });
    const catalogHeading = screen.getByRole("heading", { name: "Global set catalog" });
    expect(mapHeading.compareDocumentPosition(catalogHeading) & Node.DOCUMENT_POSITION_FOLLOWING).toBeTruthy();
    expect(screen.queryByRole("heading", { name: "Reviewed evidence sources" })).not.toBeInTheDocument();
    expect(screen.queryByRole("heading", { name: "Live discovery pulse" })).not.toBeInTheDocument();
    expect(screen.queryByText("ComicBook Perfect Order study")).not.toBeInTheDocument();
  });

  it("separates live catalog coverage from unpublished observations", () => {
    const liveCatalogOnly = {
      ...DEMO_PUBLIC_DATA,
      mode: "live",
      summary: {
        ...DEMO_PUBLIC_DATA.summary,
        globalCoverage: "No verified country-level opening samples are published yet.",
      },
      catalog: {
        ...DEMO_PUBLIC_DATA.catalog,
        setCount: 218,
      },
      observations: {
        ...DEMO_PUBLIC_DATA.observations,
        status: "empty",
        period: null,
        observedPacks: 0,
        completeOpenings: 0,
        sourceCountryContributions: 0,
        countriesObserved: 0,
        countriesWithPublishedRate: 0,
        asOf: null,
        methodologyVersion: null,
      },
      mapCells: [],
      sets: [],
      regions: [],
      retailers: [],
      batches: [],
      trend: [],
      recentActivity: [],
    } satisfies PublicDashboardData;

    render(<HomeView data={liveCatalogOnly} synthetic={false} />);

    expect(screen.getByText("Worldwide catalog and observation readiness")).toBeVisible();
    expect(screen.getByText("Live catalog")).toBeVisible();
    expect(screen.getByText("218 catalog sets are live. Verified country or product-market coverage is not published yet.")).toBeVisible();
    expect(screen.getByRole("heading", { name: "Worldwide evidence coverage" })).toBeVisible();
    expect(screen.getByText("No verified pack coverage yet")).toBeVisible();
    expect(screen.queryByRole("heading", { name: "Trending sets" })).not.toBeInTheDocument();
  });

  it("labels collecting observations as live coverage while withholding rates", () => {
    const samplePacks = [18, 24, 210] as const;
    const sampleOpenings = [5, 6, 20] as const;
    const sampleSources = [1, 2, 3] as const;
    const mixedMapCells = DEMO_PUBLIC_DATA.mapCells.slice(0, 3).map((cell, index) => ({
      ...cell,
      packsObserved: samplePacks[index] ?? 0,
      openings: sampleOpenings[index] ?? 0,
      independentSources: sampleSources[index] ?? 0,
      baselineRate: null,
      hitRate: null,
      posteriorMean: null,
      credibleInterval: null,
      deltaFromBaseline: null,
      state: index === 2 ? "pending" as const : "insufficient" as const,
      sampleNote: index === 2
        ? "Evidence threshold met; reviewed publication is pending."
        : "Rate withheld below the evidence threshold.",
    }));
    const liveCollecting = {
      ...DEMO_PUBLIC_DATA,
      mode: "live" as const,
      summary: {
        ...DEMO_PUBLIC_DATA.summary,
        observedPacks: 252,
        completeOpenings: 31,
        trackedRegions: 3,
        globalCoverage: "Three countries have verified observations; rates remain withheld.",
      },
      observations: {
        ...DEMO_PUBLIC_DATA.observations,
        status: "collecting" as const,
        observedPacks: 252,
        completeOpenings: 31,
        sourceCountryContributions: 6,
        countriesObserved: 3,
        countriesWithPublishedRate: 0,
      },
      mapCells: mixedMapCells,
    } satisfies PublicDashboardData;

    render(<HomeView data={liveCollecting} synthetic={false} />);

    expect(screen.getByText("Live observations")).toBeVisible();
    expect(screen.getByText("Verified observations cover 3 country or product-market coverage buckets and 252 packs. Exact sample rates appear only where a reviewed normalized numerator is also available; inference remains separately gated.")).toBeVisible();
    const disclosure = screen.getByText("Country and market details").closest("summary")!;
    expect(disclosure.parentElement).not.toHaveAttribute("open");
    fireEvent.click(disclosure);
    expect(screen.getByText("Inference pending")).toBeVisible();
    expect(screen.getAllByText("Withheld").length).toBeGreaterThan(0);
    expect(screen.queryByText(/Verified country or product-market coverage is not published yet/)).not.toBeInTheDocument();
  });

  it("does not publish the operational social pulse on the homepage", () => {
    const pulse: PublicSocialActivityPulse = {
      schemaVersion: "4.0.0" as const,
      window: {
        start: "2026-08-30T10:45:00Z",
        end: "2026-08-31T10:45:00Z",
      },
      activityOnly: true as const,
      nonEvidence: true as const,
      sources: [
        {
          id: "bluesky_jetstream" as const,
          name: "Bluesky Jetstream discovery" as const,
          kind: "social" as const,
          access: "public" as const,
          status: "operational" as const,
          freshness: "fresh" as const,
          lastCollectedAt: "2026-08-31T10:45:00Z",
          newCandidates24h: 12,
          retainedCandidates: 42,
          activityOnly: true as const,
          statisticsEligible: false as const,
        },
        {
          id: "nostr_multi_relay" as const,
          name: "Nostr multi-relay discovery" as const,
          kind: "social" as const,
          access: "public" as const,
          status: "delayed" as const,
          freshness: "delayed" as const,
          lastCollectedAt: "2026-08-31T10:30:00Z",
          newCandidates24h: 8,
          retainedCandidates: 18,
          activityOnly: true as const,
          statisticsEligible: false as const,
        },
        {
          id: "mastodon_public_hashtag" as const,
          name: "Mastodon public hashtag discovery" as const,
          kind: "social" as const,
          access: "public" as const,
          status: "attention" as const,
          freshness: "attention" as const,
          lastCollectedAt: null,
          newCandidates24h: 0,
          retainedCandidates: 0,
          activityOnly: true as const,
          statisticsEligible: false as const,
        },
      ],
    };

    render(<HomeView data={{ ...DEMO_PUBLIC_DATA, socialActivityPulse: pulse }} synthetic={false} />);

    expect(screen.queryByRole("group", { name: "Social activity scope" })).not.toBeInTheDocument();
    expect(screen.queryByText("New candidates (24h)")).not.toBeInTheDocument();
    for (const source of pulse.sources) {
      expect(screen.queryByText(source.name)).not.toBeInTheDocument();
    }
  });

  it("keeps source health out of the homepage regardless of availability", () => {
    const sources = [
      {
        id: "bluesky_jetstream",
        name: "Bluesky Jetstream discovery",
        kind: "social",
        access: "public",
        status: "operational",
        lastCollectedAt: "2026-08-30T10:45:00.000Z",
        url: "https://bsky.network/docs/jetstream/",
        note: "Public activity discovery only; it is never opening evidence or a pull-rate denominator.",
      },
      {
        id: "nostr_multi_relay",
        name: "Nostr multi-relay discovery",
        kind: "social",
        access: "public",
        status: "delayed",
        lastCollectedAt: null,
        url: "https://github.com/nostr-protocol/nips/blob/master/01.md",
        note: "Multi-relay activity discovery only; it is never opening evidence or a pull-rate denominator.",
      },
      {
        id: "mastodon_public_hashtag",
        name: "Mastodon public hashtag discovery",
        kind: "social",
        access: "public",
        status: "attention",
        lastCollectedAt: "2026-08-30T10:40:00.000Z",
        url: "https://docs.joinmastodon.org/methods/timelines/",
        note: "Public hashtag activity discovery only; it is never opening evidence or a pull-rate denominator.",
      },
      {
        id: "reviewed_social_evidence",
        name: "Reviewed social evidence",
        kind: "social",
        access: "public",
        status: "operational",
        lastCollectedAt: "2026-08-30T10:39:00.000Z",
        url: "https://example.com/reviewed-social-evidence",
        note: "A public social source that is not an approved discovery projection.",
      },
      {
        id: "youtube_discovery",
        name: "YouTube with a drifted access contract",
        kind: "video",
        access: "public",
        status: "operational",
        lastCollectedAt: "2026-08-30T10:38:00.000Z",
        url: "https://developers.google.com/youtube/v3",
        note: "This source must fail closed because its access contract drifted.",
      },
    ] as const;
    const liveSocialData = { ...DEMO_PUBLIC_DATA, mode: "live" as const, sources } satisfies PublicDashboardData;

    render(<HomeView data={liveSocialData} synthetic={false} />);

    expect(screen.queryByRole("heading", { name: "Live discovery pulse" })).not.toBeInTheDocument();
    for (const source of sources) {
      expect(screen.queryByText(source.name)).not.toBeInTheDocument();
    }
  });

  it("does not add an empty source-status panel when no sources exist", () => {
    const noDiscoveryData = { ...DEMO_PUBLIC_DATA, sources: [] } satisfies PublicDashboardData;

    render(<HomeView data={noDiscoveryData} synthetic={false} />);

    expect(screen.queryByText("No public discovery source status is available.")).not.toBeInTheDocument();
    expect(screen.getByRole("heading", { name: "Overview" })).toBeVisible();
  });
});
