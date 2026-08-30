import React from "react";
import { fireEvent, render, screen } from "@testing-library/react";
import { describe, expect, it } from "vitest";

import { DEMO_PUBLIC_DATA } from "@/data/demo";
import {
  buildWorldHeatRows,
  getWorldMapFill,
  WorldHeatmap,
} from "./world-heatmap";

describe("WorldHeatmap", () => {
  it("renders a global fixed-scale map with exact accessible values", () => {
    render(
      <WorldHeatmap
        cells={DEMO_PUBLIC_DATA.mapCells}
        coverageSummary={DEMO_PUBLIC_DATA.summary.globalCoverage}
        observations={DEMO_PUBLIC_DATA.observations}
      />,
    );

    expect(screen.getByRole("heading", { name: "Worldwide qualifying-hit map" })).toBeVisible();
    expect(screen.getByRole("img", { name: "Baseline delta across the world" })).toHaveAttribute(
      "preserveAspectRatio",
      "xMidYMid meet",
    );
    expect(screen.getByRole("region", { name: "Exact global country values" })).toBeVisible();
    expect(screen.getByRole("cell", { name: "Brazil BR" })).toBeVisible();
    expect(screen.getAllByText("Withheld").length).toBeGreaterThan(0);
    expect(screen.getByText(/not a global independent-source count/i)).toBeVisible();
  });

  it("switches between delta and rate without snapshot-relative normalization", () => {
    render(
      <WorldHeatmap
        cells={DEMO_PUBLIC_DATA.mapCells}
        coverageSummary={DEMO_PUBLIC_DATA.summary.globalCoverage}
        observations={DEMO_PUBLIC_DATA.observations}
      />,
    );

    fireEvent.click(screen.getByRole("button", { name: "Observed rate" }));
    expect(screen.getByRole("button", { name: "Observed rate" })).toHaveAttribute("aria-pressed", "true");
    expect(screen.getByRole("img", { name: "Observed rate across the world" })).toBeVisible();
    expect(screen.getByText("15%")).toBeVisible();

    expect(getWorldMapFill(-1, "delta")).toBe(getWorldMapFill(-0.05, "delta"));
    expect(getWorldMapFill(1, "delta")).toBe(getWorldMapFill(0.05, "delta"));
    expect(getWorldMapFill(1, "rate")).toBe(getWorldMapFill(0.3, "rate"));
  });

  it("uses a fixed pack-volume scale for coverage without publishing a rate", () => {
    const withheld = DEMO_PUBLIC_DATA.mapCells.find((cell) => cell.countryCode === "BR")!;
    const rows = buildWorldHeatRows([withheld], "coverage");

    expect(rows[0]).toMatchObject({
      metricValue: withheld.packsObserved,
      status: "observed",
    });
    expect(rows[0]?.fill).not.toBe("withheld");
    expect(getWorldMapFill(-1, "coverage")).toBe(getWorldMapFill(0, "coverage"));
    expect(getWorldMapFill(5_000, "coverage")).toBe(getWorldMapFill(1_500, "coverage"));

    render(
      <WorldHeatmap
        cells={[withheld]}
        coverageSummary="One reviewed country sample."
        initialMetric="coverage"
        observations={{
          ...DEMO_PUBLIC_DATA.observations,
          countriesObserved: 1,
          countriesWithPublishedRate: 0,
        }}
      />,
    );

    expect(screen.getByRole("heading", { name: "Worldwide evidence coverage" })).toBeVisible();
    expect(screen.getByRole("img", { name: "Observed pack coverage across the world" })).toHaveAccessibleDescription(
      /not a hit rate or representative demand/i,
    );
    expect(screen.getByText("Observed pack sample")).toBeVisible();
    expect(screen.queryByText("No country-level rates published yet")).not.toBeInTheDocument();
  });

  it("records the selected metric in the URL", () => {
    window.history.replaceState(null, "", "/?source=qa#map");
    render(
      <WorldHeatmap
        cells={DEMO_PUBLIC_DATA.mapCells}
        coverageSummary={DEMO_PUBLIC_DATA.summary.globalCoverage}
        observations={DEMO_PUBLIC_DATA.observations}
      />,
    );

    fireEvent.click(screen.getByRole("button", { name: "Pack coverage" }));
    expect(window.location.search).toBe("?source=qa&metric=coverage");
    expect(window.location.hash).toBe("#map");
  });

  it("sorts exact rows alphabetically and preserves withheld countries", () => {
    const rows = buildWorldHeatRows(DEMO_PUBLIC_DATA.mapCells, "delta");
    expect(rows.map((row) => row.cell.countryName)).toEqual([
      "Australia",
      "Brazil",
      "Germany",
      "Japan",
      "United Kingdom",
      "United States",
    ]);
    expect(rows.find((row) => row.cell.countryCode === "BR")?.status).toBe("withheld");
  });

  it("distinguishes a threshold-sufficient row awaiting reviewed publication", () => {
    const pending = {
      ...DEMO_PUBLIC_DATA.mapCells.find((cell) => cell.countryCode === "BR")!,
      independentSources: 3,
      state: "pending" as const,
      sampleNote: "Evidence threshold met; reviewed publication pending.",
    };
    render(
      <WorldHeatmap
        cells={[pending]}
        coverageSummary="One country awaits reviewed publication."
        initialMetric="delta"
        observations={{
          ...DEMO_PUBLIC_DATA.observations,
          status: "collecting",
          observedPacks: pending.packsObserved,
          completeOpenings: pending.openings,
          sourceCountryContributions: pending.independentSources,
          countriesObserved: 1,
          countriesWithPublishedRate: 0,
        }}
      />,
    );

    expect(screen.getByText("Publication pending")).toBeVisible();
    expect(screen.getByText(/met the evidence threshold and await reviewed publication/i)).toBeVisible();
  });

  it("shows an honest neutral empty state", () => {
    render(
      <WorldHeatmap
        cells={[]}
        coverageSummary="No verified country-level opening samples are published yet."
        observations={{
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
        }}
      />,
    );
    expect(screen.getByText("Awaiting observations")).toBeVisible();
    expect(screen.getByText("No verified pack coverage yet")).toBeVisible();
    expect(screen.getByText("No verified country observations are published yet.")).toBeVisible();
    expect(screen.getByRole("img", { name: "Observed pack coverage across the world" })).toHaveAccessibleDescription(
      /every country is shown in the neutral no-data colour/i,
    );
  });
});
