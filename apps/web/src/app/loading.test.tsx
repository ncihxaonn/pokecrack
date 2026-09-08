import React from "react";
import { render, screen } from "@testing-library/react";
import { describe, expect, it } from "vitest";

import Loading from "./loading";

describe("Public loading shell", () => {
  it("announces loading while keeping decorative placeholders out of the accessibility tree", () => {
    const { container } = render(<Loading />);
    expect(screen.getByRole("status")).toHaveTextContent("Loading dashboard data");
    expect(container.firstElementChild).toHaveAttribute("aria-busy", "true");
    expect(container.querySelector(".loading-workspace")?.closest('[aria-hidden="true"]')).not.toBeNull();
    expect(screen.queryByRole("img")).not.toBeInTheDocument();
    expect(screen.queryByRole("button")).not.toBeInTheDocument();
  });
});
