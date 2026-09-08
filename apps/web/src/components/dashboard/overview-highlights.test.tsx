import React from "react";
import { render, screen, within } from "@testing-library/react";
import { describe, expect, it } from "vitest";
import { DEMO_PUBLIC_DATA } from "@/data/demo";
import { OverviewHighlights } from "./overview-highlights";

describe("OverviewHighlights", () => {
  it("ranks published region counts without changing the input or inventing rates", () => {
    const original = DEMO_PUBLIC_DATA.regions.map((region) => region.slug);
    render(<OverviewHighlights data={DEMO_PUBLIC_DATA} />);
    const packs = screen.getByRole("article", { name: "Observed packs" });
    const rows = within(packs).getAllByRole("listitem");
    const expected = [...DEMO_PUBLIC_DATA.regions].filter((region) => region.packsObserved > 0)
      .sort((a, b) => b.packsObserved - a.packsObserved || a.name.localeCompare(b.name)).slice(0, 5);
    expect(rows).toHaveLength(expected.length);
    for (const [index, region] of expected.entries()) {
      expect(rows[index]).toHaveTextContent(region.name);
      expect(rows[index]).toHaveTextContent(new Intl.NumberFormat("en-AU").format(region.packsObserved));
    }
    expect(DEMO_PUBLIC_DATA.regions.map((region) => region.slug)).toEqual(original);
    expect(packs).not.toHaveTextContent("%");
  });

  it("shows explicit empty charts when no region observations are published", () => {
    render(<OverviewHighlights data={{ ...DEMO_PUBLIC_DATA, regions: [] }} />);
    for (const name of ["Observed packs", "Complete openings"]) {
      const chart = screen.getByRole("article", { name });
      expect(within(chart).getByText("No published comparison available.")).toBeVisible();
      expect(within(chart).queryByRole("list")).not.toBeInTheDocument();
    }
  });

  it("labels catalog preview entries separately from the full catalog count", () => {
    const sets = DEMO_PUBLIC_DATA.catalog.sets.slice(0, 2).map((set) => ({ ...set, series: "Example series" }));
    render(<OverviewHighlights data={{ ...DEMO_PUBLIC_DATA, catalog: { ...DEMO_PUBLIC_DATA.catalog, sets, setCount: 999 } }} />);
    const catalog = screen.getByRole("article", { name: "Catalog sets" });
    expect(catalog).toHaveTextContent("2 displayed catalog entries · Metadata only");
    expect(within(catalog).getAllByRole("listitem")).toHaveLength(1);
    expect(catalog).toHaveTextContent("Example series");
    expect(catalog).not.toHaveTextContent("999");
  });
});
