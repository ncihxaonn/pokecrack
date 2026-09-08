import React from "react";
import { render, screen } from "@testing-library/react";
import { describe, expect, it } from "vitest";

import { BRAND } from "@/config/brand";
import { AppFooter } from "./app-footer";

describe("AppFooter", () => {
  it("keeps the disclaimer without public reference navigation", () => {
    render(<AppFooter />);

    expect(screen.getByText(BRAND.footerDisclaimer)).toBeVisible();
    expect(screen.getByText(BRAND.copyright)).toBeVisible();
    expect(screen.queryByRole("navigation")).not.toBeInTheDocument();
    expect(screen.queryByRole("link")).not.toBeInTheDocument();
  });
});
