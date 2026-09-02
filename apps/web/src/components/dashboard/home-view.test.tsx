import React from "react";
import { render, screen } from "@testing-library/react";
import { describe, expect, it } from "vitest";

import { BRAND } from "@/config/brand";
import { DEMO_PUBLIC_DATA } from "@/data/demo";
import type { PublicDashboardData, PublicSocialActivityPulse } from "@/data/types";
import { getSignalPresentation } from "@/lib/signals";
import { HomeView } from "./home-view";

describe("HomeView", () => {
  it("renders the required synthetic dashboard sections and observational caveats", () => {
    render(<HomeView data={DEMO_PUBLIC_DATA} synthetic />);

    expect(screen.getByRole("heading", { level: 1, name: BRAND.tagline })).toBeVisible();
    expect(screen.getByText(BRAND.demoNotice)).toBeVisible();
    expect(screen.getByText(BRAND.individualPackDisclaimer)).toBeVisible();
    expect(screen.getByRole("heading", { name: "Worldwide qualifying-hit map" })).toBeVisible();
    expect(screen.getByRole("heading", { name: "Live discovery pulse" })).toBeVisible();
    expect(screen.getByText("No public social activity pulse is available.")).toBeVisible();
    expect(screen.getByText(/fixed absolute colour scale/i)).toBeVisible();
    expect(screen.getByRole("heading", { name: "Global set catalog" })).toBeVisible();
    expect(screen.getByText(/never opening evidence or a pull-rate denominator/i)).toBeVisible();
    expect(screen.getByRole("heading", { name: "Trending sets" })).toBeVisible();
    expect(screen.getByRole("heading", { name: "Signal watch" })).toBeVisible();
    expect(screen.getByRole("heading", { name: "Recent observed activity" })).toBeVisible();
    expect(screen.getByRole("heading", { name: "Methodology at a glance" })).toBeVisible();
    expect(screen.getAllByText(getSignalPresentation("anomaly").label).length).toBeGreaterThan(0);
    expect(screen.getAllByText("4,872").length).toBeGreaterThan(0);

    const mapHeading = screen.getByRole("heading", { name: "Worldwide qualifying-hit map" });
    const trendHeading = screen.getByRole("heading", { name: "Observed trend" });
    expect(mapHeading.compareDocumentPosition(trendHeading) & Node.DOCUMENT_POSITION_FOLLOWING).toBeTruthy();
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
    expect(screen.getByText("218 catalog sets are live. Verified country observations are not published yet.")).toBeVisible();
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
    expect(screen.getByText("Verified observations cover 3 countries and 252 packs; country-level rates remain withheld until evidence thresholds and reviewed publication are satisfied.")).toBeVisible();
    expect(screen.getByText("Publication pending")).toBeVisible();
    expect(screen.getAllByText("Withheld").length).toBeGreaterThan(0);
    expect(screen.queryByText(/Verified country observations are not published yet/)).not.toBeInTheDocument();
  });

  it("renders platform-specific social activity counts with explicit non-evidence labels", () => {
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

    expect(screen.getAllByText("Activity only").length).toBeGreaterThanOrEqual(3);
    expect(screen.getByText("Non-evidence")).toBeVisible();
    expect(screen.getAllByText("New candidates (24h)")).toHaveLength(3);
    expect(screen.getByText("Bluesky Jetstream discovery")).toBeVisible();
    expect(screen.getByText("Nostr multi-relay discovery")).toBeVisible();
    expect(screen.getByText("Mastodon public hashtag discovery")).toBeVisible();
    expect(screen.getByText("12")).toBeVisible();
    expect(screen.getByText("42")).toBeVisible();
    expect(screen.getByText("8")).toBeVisible();
    expect(screen.getByText("18")).toBeVisible();
    expect(screen.getByText(/not evidence for packs, country, or rate/i)).toBeVisible();
    expect(screen.queryByRole("link", { name: /Bluesky Jetstream discovery/i })).not.toBeInTheDocument();
  });
});
