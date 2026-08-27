import React from "react";
import { fireEvent, render, screen, within } from "@testing-library/react";
import { describe, expect, it, vi } from "vitest";

import { DEMO_PUBLIC_DATA } from "@/data/demo";
import type { RegionMetric } from "@/data/types";
import { buildRegionHeatRows, RegionHeatmap } from "./region-heatmap";

vi.mock("./regional-map", () => ({
  RegionalMap: () => <div role="img" aria-label="Australia state and territory choropleth" data-testid="australia-region-map" />,
}));

describe("RegionHeatmap", () => {
  it("renders an Australia state choropleth with exact accessible regional values", () => {
    render(<RegionHeatmap regions={DEMO_PUBLIC_DATA.regions} />);

    expect(screen.getByRole("heading", { name: "Observed regional pull map" })).toBeVisible();
    expect(screen.getByRole("img", { name: /australia state and territory choropleth/i })).toBeVisible();
    expect(screen.getByTestId("australia-region-map")).toBeVisible();
    expect(screen.queryByTestId("dotted-world-map")).not.toBeInTheDocument();
    expect(screen.getByText(/current published coverage is Australia-only/i)).toBeVisible();
    expect(screen.getByRole("button", { name: "Observed rate" })).toHaveAttribute("aria-pressed", "true");
    expect(screen.getByRole("link", { name: /VIC \/ Melbourne: 16\.1%/i })).toHaveAttribute("href", "/regions/au-vic-melbourne");
    expect(screen.getByRole("link", { name: /NSW \/ Sydney: 14\.9%/i })).toBeVisible();
    expect(screen.queryByText(/lucky|best place|future odds/i)).not.toBeInTheDocument();
  });

  it("switches the visible ranking metric without hiding the text fallback", () => {
    render(<RegionHeatmap regions={DEMO_PUBLIC_DATA.regions} />);

    fireEvent.click(screen.getByRole("button", { name: "Sample volume" }));

    expect(screen.getByRole("button", { name: "Sample volume" })).toHaveAttribute("aria-pressed", "true");
    expect(screen.getByRole("link", { name: /NSW \/ Sydney: 1\.5K packs/i })).toBeVisible();
    const rail = screen.getByRole("complementary", { name: "Published regional observations" });
    const links = within(rail).getAllByRole("link");
    expect(links).toHaveLength(DEMO_PUBLIC_DATA.regions.length + 1);
    expect(links[0]).toHaveAccessibleName(/NSW \/ Sydney: 1\.5K packs/i);
    expect(screen.getByRole("status")).toHaveTextContent("Sample volume selected; regional ranking updated.");
  });

  it("keeps unknown coordinates in the list and treats withheld values as withheld", () => {
    const unknown: RegionMetric = {
      ...DEMO_PUBLIC_DATA.regions[0]!,
      slug: "au-unknown-demo",
      name: "Australia · Unmapped demo region",
      coverage: "Unmapped Australian demo coverage",
      packsObserved: 12,
      openings: 2,
      independentSources: 1,
      baselineRate: null,
      hitRate: null,
      posteriorMean: null,
      credibleInterval: null,
      deltaFromBaseline: null,
      state: "insufficient",
      sampleNote: "Insufficient evidence; estimates are withheld.",
    };

    render(<RegionHeatmap regions={[unknown]} />);

    const link = screen.getByRole("link", { name: /Unmapped demo region: Withheld/i });
    expect(link).toBeVisible();
    expect(within(link).getByText("Withheld")).toBeVisible();
    expect(screen.getByText("No published values")).toBeVisible();
    expect(screen.getByText(/1 region is listed without a map anchor/i)).toBeVisible();
  });

  it("renders a directed empty state", () => {
    render(<RegionHeatmap regions={[]} />);
    expect(screen.getByText("No region aggregates are published in this snapshot.")).toBeVisible();
  });
});

describe("buildRegionHeatRows", () => {
  it("sorts deterministically without mutating the source array", () => {
    const source = [...DEMO_PUBLIC_DATA.regions];
    const originalOrder = source.map((region) => region.slug);
    const rows = buildRegionHeatRows(source, "rate");

    expect(rows[0]!.region.slug).toBe("au-vic-melbourne");
    expect(rows.at(-1)?.region.slug).toBe("au-wa-perth");
    expect(source.map((region) => region.slug)).toEqual(originalOrder);
    expect(rows.every((row) => row.normalized === null || (row.normalized >= 0 && row.normalized <= 1))).toBe(true);
  });

  it("uses a stable midpoint when every value is equal", () => {
    const equal = DEMO_PUBLIC_DATA.regions.map((region) => ({ ...region, hitRate: 0.15 }));
    expect(buildRegionHeatRows(equal, "rate").every((row) => row.normalized === 0.5)).toBe(true);
  });
});
