import React from "react";
import { existsSync } from "node:fs";
import path from "node:path";
import { fireEvent, render, screen } from "@testing-library/react";
import { describe, expect, it } from "vitest";

import { BRAND } from "@/config/brand";

const appDirectory = path.resolve(process.cwd(), "src/app");
const shellFiles = [
  "layout.tsx",
  "globals.css",
  "loading.tsx",
  "error.tsx",
  "not-found.tsx",
  "_components/site-chrome.tsx",
] as const;

describe("App Router shell", () => {
  it("provides the complete root route shell", async () => {
    const missing = shellFiles.filter((file) => !existsSync(path.join(appDirectory, file)));
    expect(missing).toEqual([]);
    if (missing.length > 0) return;

    const modulePath = "./_components/site-chrome";
    const { SiteFooter, SiteHeader } = await import(/* @vite-ignore */ modulePath);
    const { unmount } = render(<SiteHeader />);
    expect(screen.getByRole("navigation", { name: "Primary navigation" })).toBeVisible();
    fireEvent.click(screen.getByText("Menu"));
    expect(screen.getByRole("navigation", { name: "Mobile navigation" })).toBeVisible();
    expect(screen.getAllByRole("link", { name: "Sets" })[0]).toHaveAttribute("href", "/sets");
    unmount();

    render(<SiteFooter />);
    expect(screen.getByText(BRAND.footerDisclaimer)).toBeVisible();
    expect(screen.getByText(BRAND.copyright)).toBeVisible();
  });
});
