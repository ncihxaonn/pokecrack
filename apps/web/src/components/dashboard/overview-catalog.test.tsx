import React from "react";
import { fireEvent, render, screen } from "@testing-library/react";
import { describe, expect, it } from "vitest";
import { DEMO_PUBLIC_DATA } from "@/data/demo";
import { OverviewCatalog } from "./overview-catalog";

const sets = Array.from({ length: 15 }, (_, index) => ({ ...DEMO_PUBLIC_DATA.catalog.sets[0]!, id: `set-${index}`, slug: `set-${index}`, name: `Set ${String(index).padStart(2, "0")}`, series: null, releaseDate: null }));
const catalog = { ...DEMO_PUBLIC_DATA.catalog, sets, setCount: 15 };

describe("OverviewCatalog", () => {
  it("paginates every available entry without empty metadata columns or internal slugs", () => {
    render(<OverviewCatalog catalog={catalog} />);
    expect(screen.getByText("Set 00")).toBeVisible();
    expect(screen.queryByText("Set 14")).not.toBeInTheDocument();
    expect(screen.queryByRole("columnheader", { name: "Series" })).not.toBeInTheDocument();
    expect(screen.queryByRole("columnheader", { name: "Release" })).not.toBeInTheDocument();
    expect(screen.queryByText("set-0")).not.toBeInTheDocument();
    fireEvent.click(screen.getByRole("button", { name: "Next" }));
    expect(screen.getByText("Set 14")).toBeVisible();
    expect(screen.getByRole("button", { name: "Next" })).toBeDisabled();
    fireEvent.change(screen.getByRole("searchbox", { name: "Search catalog" }), { target: { value: "set 01" } });
    expect(screen.getByText("Set 01")).toBeVisible();
    expect(screen.getByRole("status")).toHaveTextContent("1–1 of 1");
    expect(screen.getByRole("button", { name: "Previous" })).toBeDisabled();
  });
  it("labels bounded snapshots honestly and handles unmatched search", () => {
    render(<OverviewCatalog catalog={{ ...catalog, setCount: 220 }} />);
    expect(screen.getByRole("status")).toHaveTextContent("15 of 220 entries available in this snapshot");
    fireEvent.change(screen.getByRole("searchbox", { name: "Search catalog" }), { target: { value: "no matching set" } });
    expect(screen.getByText("No catalog entries match this search.")).toBeVisible();
    expect(screen.getByRole("button", { name: "Next" })).toBeDisabled();
  });
});
