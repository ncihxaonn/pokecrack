import React from "react";
import { fireEvent, render, screen, within } from "@testing-library/react";
import { describe, expect, it, vi } from "vitest";
import { AppHeader } from "./app-header";

const route = vi.hoisted(() => ({ pathname: "/regions/japan" }));
vi.mock("next/navigation", () => ({ usePathname: () => route.pathname }));

describe("AppHeader", () => {
  it("shows only the five research destinations on desktop and mobile", () => {
    const { container } = render(<AppHeader />);
    fireEvent.click(screen.getByText("Menu"));
    for (const name of ["Primary navigation", "Mobile navigation"]) {
      const links = within(screen.getByRole("navigation", { name })).getAllByRole("link");
      expect(links.map((link) => link.textContent)).toEqual(["Overview", "Sets", "Regions", "Retailers", "Batches"]);
    }
    expect(container.querySelector('a[href="/sources"], a[href="/methodology"], a[href="/status"]')).toBeNull();
  });

  it("marks a detail route's section as current and keeps search scoped to sets", () => {
    render(<AppHeader />);
    const navigation = screen.getByRole("navigation", { name: "Primary navigation" });
    expect(within(navigation).getByRole("link", { name: "Regions" })).toHaveAttribute("aria-current", "page");
    expect(within(navigation).getByRole("link", { name: "Overview" })).not.toHaveAttribute("aria-current");
    expect(screen.getByRole("search", { name: "Find observed sets" })).toHaveAttribute("action", "/sets");
  });

  it("closes the mobile disclosure after choosing a destination", () => {
    render(<AppHeader />);
    const menu = screen.getByText("Menu");
    fireEvent.click(menu);
    expect(menu.parentElement).toHaveAttribute("open");
    fireEvent.click(within(screen.getByRole("navigation", { name: "Mobile navigation" })).getByRole("link", { name: "Sets" }));
    expect(menu.parentElement).not.toHaveAttribute("open");
  });

  it("uses the admin layout variant without marking a public route active", () => {
    route.pathname = "/admin/jobs";
    const { container } = render(<AppHeader />);
    expect(container.querySelector("header")).toHaveClass("app-header--admin");
    expect(container.querySelector('[aria-current="page"]')).toBeNull();
    route.pathname = "/regions/japan";
  });
});
