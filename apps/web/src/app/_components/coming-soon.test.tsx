import React from "react";
import { readFileSync } from "node:fs";
import path from "node:path";
import { render, screen } from "@testing-library/react";
import { describe, expect, it } from "vitest";

import SetsLayout from "../sets/layout";
import RegionsLayout from "../regions/layout";
import RetailersLayout from "../retailers/layout";
import BatchesLayout from "../batches/layout";

describe("temporary public section previews", () => {
  it.each([
    ["Sets", SetsLayout],
    ["Regions", RegionsLayout],
    ["Retailers", RetailersLayout],
    ["Batches", BatchesLayout],
  ] as const)("masks %s and all of its nested page content", (_name, Layout) => {
    const { container } = render(
      <Layout>
        <h1>Original page</h1>
        <a href="/sets/example">Original detail link</a>
        <input aria-label="Original filter" />
      </Layout>,
    );

    expect(screen.getByRole("heading", { name: "Coming soon", level: 1 })).toBeVisible();
    expect(screen.getByRole("link", { name: "Back to Overview" })).toHaveAttribute("href", "/");
    expect(screen.queryByRole("heading", { name: "Original page" })).not.toBeInTheDocument();
    expect(screen.queryByRole("link", { name: "Original detail link" })).not.toBeInTheDocument();
    expect(screen.queryByRole("textbox", { name: "Original filter" })).not.toBeInTheDocument();
    expect(container.querySelector('[inert][aria-hidden="true"]')).toContainElement(screen.getByText("Original page"));
  });

  it("keeps the shared shell, Overview and admin outside the temporary mask", () => {
    for (const file of ["layout.tsx", "page.tsx", "admin/layout.tsx"]) {
      const source = readFileSync(path.resolve(process.cwd(), "src/app", file), "utf8");
      expect(source).not.toContain("ComingSoon");
    }
  });
});
