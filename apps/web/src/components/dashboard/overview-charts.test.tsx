import React from "react";
import { fireEvent, render, screen, within } from "@testing-library/react";
import { describe, expect, it } from "vitest";
import { DEMO_PUBLIC_DATA } from "@/data/demo";
import type { CoverageRow } from "@/lib/overview-charts";
import { OverviewCharts } from "./overview-charts";

const rows: CoverageRow[] = [
  { code: "AU", name: "Australia", packs: 1200, openings: 2, attribution: "Opening location" },
  { code: "JP", name: "Japan", packs: 29, openings: 10, attribution: "Product market" },
];
const observations = { ...DEMO_PUBLIC_DATA.observations, observedPacks: 2000, completeOpenings: 20, unknownLocation: { packsObserved: 771, openings: 8, independentSources: 1, updatedAt: DEMO_PUBLIC_DATA.generatedAt } };

describe("OverviewCharts interactions", () => {
  it("switches count metrics and filters the actual published rows", () => {
    render(<OverviewCharts rows={rows} observations={observations} />);
    expect(within(screen.getByRole("list", { name: "Country ranking by packs" })).getAllByRole("listitem")[0]).toHaveTextContent("Australia");
    fireEvent.click(within(screen.getByRole("group", { name: "Ranking metric" })).getByRole("button", { name: "Openings" }));
    expect(within(screen.getByRole("list", { name: "Country ranking by openings" })).getAllByRole("listitem")[0]).toHaveTextContent("Japan");
    fireEvent.change(screen.getByRole("searchbox", { name: "Find a country or market" }), { target: { value: "AU" } });
    expect(within(screen.getByRole("list", { name: "Country ranking by openings" })).getAllByRole("listitem")).toHaveLength(1);
  });
  it("links range filtering, ranking selection and keyboard scatter selection", () => {
    const { container } = render(<OverviewCharts rows={rows} observations={observations} />);
    fireEvent.focus(screen.getByRole("button", { name: "Japan: 29 packs, 10 openings" }));
    expect(container.querySelector('[aria-live="polite"]')).toHaveTextContent("Japan");
    expect(container.querySelector('[aria-live="polite"]')).toHaveTextContent("Product market");
    fireEvent.click(within(screen.getByRole("group", { name: "Filter countries by pack count" })).getByRole("button", { name: /1,000\+ packs/ }));
    expect(screen.queryByRole("button", { name: "Japan: 29 packs, 10 openings" })).not.toBeInTheDocument();
    expect(container.querySelector('[aria-live="polite"]')).toHaveTextContent("Australia");
    fireEvent.click(screen.getByRole("button", { name: /Clear filter/ }));
    expect(screen.getByRole("button", { name: "Japan: 29 packs, 10 openings" })).toBeVisible();
  });
  it("shows the explicit global breakdown for both available metrics", () => {
    render(<OverviewCharts rows={rows} observations={observations} />);
    expect(screen.getByRole("img", { name: "1,229 attributed packs; 771 packs with unknown location" })).toBeVisible();
    fireEvent.click(within(screen.getByRole("group", { name: "Global volume metric" })).getByRole("button", { name: "Openings" }));
    expect(screen.getByRole("img", { name: "12 attributed openings; 8 openings with unknown location" })).toBeVisible();
    expect(screen.getByText("Location unknown")).toBeVisible();
  });
  it("does not invent observations or a breakdown for an empty snapshot", () => {
    render(<OverviewCharts rows={[]} observations={{ ...observations, observedPacks: 0, completeOpenings: 0, unknownLocation: null }} />);
    expect(screen.queryByRole("img")).not.toBeInTheDocument();
    expect(screen.getByText("No location breakdown is published for this snapshot.")).toBeVisible();
    expect(screen.getAllByText("No published buckets match these filters.")).toHaveLength(2);
  });
  it("limits the ranking without dropping the remaining published buckets", () => {
    const many = Array.from({ length: 21 }, (_, index) => ({ ...rows[0]!, code: `C${index}`, name: `Country ${index}`, packs: index + 1 }));
    render(<OverviewCharts rows={many} observations={observations} />);
    expect(within(screen.getByRole("list")).getAllByRole("listitem")).toHaveLength(10);
    fireEvent.change(screen.getByRole("combobox", { name: "Ranking length" }), { target: { value: "249" } });
    expect(within(screen.getByRole("list")).getAllByRole("listitem")).toHaveLength(21);
  });
});
