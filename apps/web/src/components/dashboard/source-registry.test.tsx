import React from "react";
import { fireEvent, render, screen, within } from "@testing-library/react";
import { describe, expect, it } from "vitest";

import { DEMO_PUBLIC_DATA } from "@/data/demo";
import type { PublicSource } from "@/data/types";
import { SourceRegistry } from "./source-registry";

const sources: PublicSource[] = [
  { ...DEMO_PUBLIC_DATA.sources[0]!, id: "alpha", name: "Alpha study", kind: "community", access: "public", status: "operational", note: "Reviewed opening sample", coverage: { packsObserved: 55, completeOpenings: 1, countriesObserved: 1, qualifyingHitPacks: 1, ratePacksObserved: 55, observedRate: 1 / 55 } },
  { ...DEMO_PUBLIC_DATA.sources[0]!, id: "beta", name: "Beta discovery", kind: "social", access: "public", status: "delayed", note: "Discovery is not opening evidence", coverage: undefined },
];

describe("SourceRegistry", () => {
  it("keeps details collapsed until requested, then exposes exact sample counts", () => {
    render(<SourceRegistry sources={sources} />);
    expect(screen.getByText("1 / 55")).not.toBeVisible();
    fireEvent.click(screen.getByText("Alpha study"));
    expect(screen.getByText("1 / 55")).toBeVisible();
    expect(screen.getByText("1.8%")).toBeVisible();
    expect(within(screen.getByText("Alpha study").closest("details")!).getByRole("link", { name: /Source reference/ })).toHaveAttribute("rel", "noopener noreferrer");
  });

  it("combines text, type and availability filters and can clear an empty result", () => {
    render(<SourceRegistry sources={sources} />);
    fireEvent.change(screen.getByRole("searchbox", { name: "Search sources" }), { target: { value: "  ALPHA  " } });
    expect(screen.getByRole("status")).toHaveTextContent("1 of 2 public sources");
    expect(screen.queryByText("Beta discovery")).not.toBeInTheDocument();
    fireEvent.change(screen.getByRole("combobox", { name: "Source type" }), { target: { value: "community" } });
    fireEvent.change(screen.getByRole("combobox", { name: "Availability" }), { target: { value: "delayed" } });
    expect(screen.getByRole("status")).toHaveTextContent("0 of 2 public sources");
    expect(screen.getByText(/No sources match/)).toBeVisible();
    fireEvent.click(screen.getByRole("button", { name: "Clear" }));
    expect(within(screen.getByRole("list", { name: "Registered public sources" })).getAllByRole("listitem")).toHaveLength(2);
    expect(screen.getByRole("searchbox")).toHaveValue("");
  });

  it("does not promote discovery to opening evidence", () => {
    render(<SourceRegistry sources={[{ ...sources[1]!, coverage: sources[0]!.coverage }]} />);
    fireEvent.click(screen.getByText("Beta discovery"));
    expect(screen.getByText("Discovery is not opening evidence")).toBeVisible();
    expect(screen.queryByText("Observed packs")).not.toBeInTheDocument();
  });

  it("renders an honest empty registry", () => {
    render(<SourceRegistry sources={[]} />);
    expect(screen.getByText("No public source status is available.")).toBeVisible();
    expect(screen.getByRole("status")).toHaveTextContent("0 of 0 public sources");
  });
});
