import React from "react";
import { render, screen } from "@testing-library/react";
import { describe, expect, it } from "vitest";

import type { PublicSource } from "@/data/types";
import { ReviewedEvidenceSources } from "./reviewed-evidence-sources";

const reviewedSource: PublicSource = {
  id: "comicbook_perfect_order_study",
  name: "ComicBook Perfect Order study",
  kind: "community",
  access: "public",
  status: "operational",
  lastCollectedAt: "2026-09-03T01:00:00.000Z",
  url: "https://comicbook.com/example",
  note: "Reviewed opening sample.",
  coverage: {
    packsObserved: 55,
    countriesObserved: 1,
    completeOpenings: 1,
  },
};

describe("ReviewedEvidenceSources", () => {
  it("shows reviewed denominator coverage without presenting it as a hit rate", () => {
    render(
      <ReviewedEvidenceSources
        sources={[
          reviewedSource,
          {
            id: "bluesky_jetstream",
            name: "Bluesky Jetstream discovery",
            kind: "social",
            access: "public",
            status: "operational",
            lastCollectedAt: "2026-09-03T01:00:00.000Z",
            url: "https://bsky.network/docs/jetstream/",
            note: "Activity only; never opening evidence.",
            coverage: {
              packsObserved: 55,
              countriesObserved: 1,
              completeOpenings: 1,
            },
          },
        ]}
      />,
    );

    expect(screen.getByRole("heading", { name: "Reviewed evidence sources" })).toBeVisible();
    expect(screen.getByText(/not a hit rate/i)).toBeVisible();
    expect(screen.getByText("55 packs")).toBeVisible();
    expect(screen.getByText("Attributed countries")).toBeVisible();
    expect(screen.getByText("1 country")).toBeVisible();
    expect(screen.getByText("1 opening")).toBeVisible();
    expect(screen.getByText("03 Sep 2026, 01:00 UTC").tagName).toBe("TIME");
    expect(screen.getByRole("link", { name: /ComicBook Perfect Order study/ })).toHaveAttribute(
      "href",
      "https://comicbook.com/example",
    );
    expect(screen.queryByText("Bluesky Jetstream discovery")).not.toBeInTheDocument();
  });

  it("stays out of the layout when no reviewed coverage is available", () => {
    const { container } = render(<ReviewedEvidenceSources sources={[]} />);

    expect(container).toBeEmptyDOMElement();
    expect(screen.queryByText(/0 packs/i)).not.toBeInTheDocument();
  });
});
