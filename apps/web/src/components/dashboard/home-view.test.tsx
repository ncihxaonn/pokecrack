import React from "react";
import { render, screen } from "@testing-library/react";
import { describe, expect, it } from "vitest";

import { BRAND } from "@/config/brand";
import { DEMO_PUBLIC_DATA } from "@/data/demo";
import type { PublicDashboardData } from "@/data/types";
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
    expect(screen.getByRole("link", { name: /YouTube Data API/ })).toHaveAttribute(
      "href",
      "https://developers.google.com/youtube/v3",
    );
    expect(screen.getByText("Discovery metadata; extracted observations require validation.")).toBeVisible();
    expect(screen.queryByRole("link", { name: /Reddit authenticated session/ })).not.toBeInTheDocument();
    expect(screen.queryByRole("link", { name: /X authenticated session/ })).not.toBeInTheDocument();
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

  it("shows public social discovery health without turning activity into evidence", () => {
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
    ] as const;
    const liveSocialData = { ...DEMO_PUBLIC_DATA, mode: "live" as const, sources } satisfies PublicDashboardData;

    render(<HomeView data={liveSocialData} synthetic={false} />);

    expect(screen.getByRole("heading", { name: "Live discovery pulse" })).toBeVisible();
    expect(screen.getByRole("link", { name: /Bluesky Jetstream discovery/ })).toHaveAttribute(
      "href",
      "https://bsky.network/docs/jetstream/",
    );
    expect(screen.getByText("operational", { selector: "span" })).toBeVisible();
    expect(screen.getByText("30 Aug 2026, 10:45 UTC")).toBeVisible();
    expect(screen.getByText("Public activity discovery only; it is never opening evidence or a pull-rate denominator.")).toBeVisible();
  });

  it("renders an honest empty state when no public discovery source is projected", () => {
    const noDiscoveryData = { ...DEMO_PUBLIC_DATA, sources: [] } satisfies PublicDashboardData;

    render(<HomeView data={noDiscoveryData} synthetic={false} />);

    expect(screen.getByText("No public discovery source status is available.")).toBeVisible();
  });
});
