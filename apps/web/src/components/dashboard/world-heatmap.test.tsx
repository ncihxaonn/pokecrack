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
        observations={DEMO_PUBLIC_DATA.observations}
      />,
    );

    expect(screen.getByRole("heading", { name: "Worldwide qualifying-hit map" })).toBeVisible();
    expect(screen.getByRole("img", { name: "Baseline delta across the world" })).toBeVisible();
    expect(screen.getByRole("region", { name: "Exact global country values" })).toBeVisible();
    expect(screen.getByRole("cell", { name: "Brazil BR" })).toBeVisible();
    expect(screen.getAllByText("Withheld").length).toBeGreaterThan(0);
    expect(screen.getByText(/not labelled as a global independent-source count/i)).toBeVisible();
  });

  it("switches between delta and rate without snapshot-relative normalization", () => {
    render(
      <WorldHeatmap
        cells={DEMO_PUBLIC_DATA.mapCells}
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

  it("shows an honest neutral empty state", () => {
    render(
      <WorldHeatmap
        cells={[]}
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
    expect(screen.getByText("No verified country observations are published yet.")).toBeVisible();
    expect(screen.getByRole("img", { name: "Baseline delta across the world" })).toHaveAccessibleDescription(
      /every country is shown in the neutral no-data colour/i,
    );
  });
});
