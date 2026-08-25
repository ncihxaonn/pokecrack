import React from "react";
import { render, screen } from "@testing-library/react";
import { describe, expect, it } from "vitest";

import { BRAND } from "@/config/brand";
import { AppFooter } from "./app-footer";

describe("AppFooter", () => {
  it("renders the centralized exact disclaimer and public reference links", () => {
    render(<AppFooter />);

    expect(screen.getByText(BRAND.footerDisclaimer)).toBeVisible();
    expect(screen.getByText(BRAND.copyright)).toBeVisible();
    expect(screen.getByRole("link", { name: "Methodology" })).toHaveAttribute(
      "href",
      "/methodology",
    );
    expect(screen.getByRole("link", { name: "Sources" })).toHaveAttribute(
      "href",
      "/sources",
    );
    expect(screen.getByRole("link", { name: "System status" })).toHaveAttribute(
      "href",
      "/status",
    );
  });
});
