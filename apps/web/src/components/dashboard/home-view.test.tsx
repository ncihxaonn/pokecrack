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
});
