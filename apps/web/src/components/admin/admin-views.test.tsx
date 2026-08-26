import React from "react";
import { cleanup, render, screen } from "@testing-library/react";
import { afterEach, describe, expect, it } from "vitest";

import { ADMIN_DEMO_FIXTURE, type AdminStatusData } from "@/app/admin/_lib/admin-fixture";
import {
  AdminAiUsageView,
  AdminBrowserView,
  AdminJobsView,
  AdminModeNotice,
  AdminOverview,
  AdminSourcesView,
  AdminSystemView,
} from "./admin-views";

afterEach(cleanup);

describe("admin demo views", () => {
  it("uses the complete read-only operational fixture across all admin pages", () => {
    const overview = render(<AdminOverview snapshot={{ status: "ready", data: ADMIN_DEMO_FIXTURE }} />);
    expect(screen.getByText("Pipeline accepted")).toBeVisible();
    expect(screen.getByText("Aggregator")).toBeVisible();
    expect(screen.getByText("Cross-posted opening")).toBeVisible();
    overview.unmount();

    const sources = render(<AdminSourcesView data={ADMIN_DEMO_FIXTURE} />);
    expect(screen.getByText("YouTube metadata")).toBeVisible();
    expect(screen.getByText("OpenCLI western social")).toBeVisible();
    sources.unmount();

    const jobs = render(<AdminJobsView data={ADMIN_DEMO_FIXTURE} />);
    expect(screen.getByText("Evidence validation")).toBeVisible();
    expect(screen.getByText("3 / 3")).toBeVisible();
    jobs.unmount();

    const browser = render(<AdminBrowserView data={ADMIN_DEMO_FIXTURE} />);
    expect(screen.getByText("Chinese social session")).toBeVisible();
    expect(screen.getByText("expired")).toBeVisible();
    browser.unmount();

    const ai = render(<AdminAiUsageView data={ADMIN_DEMO_FIXTURE} />);
    expect(screen.getByText("Estimated / budget")).toBeVisible();
    expect(screen.getByText("$4.92 / $10.00")).toBeVisible();
    ai.unmount();

    const liveData = {
      ...ADMIN_DEMO_FIXTURE,
      fixture: false,
      ai: { ...ADMIN_DEMO_FIXTURE.ai, budgetAud: null, paused: false },
    } satisfies AdminStatusData;
    const liveAi = render(<AdminAiUsageView data={liveData} />);
    expect(screen.getByText("budget not reported")).toBeVisible();
    expect(screen.queryByText("within configured budget")).not.toBeInTheDocument();
    liveAi.unmount();

    const liveMode = render(<AdminModeNotice message="Live snapshot loaded." status="ready" synthetic={false} />);
    expect(screen.getByText("LIVE / READ ONLY")).toBeVisible();
    liveMode.unmount();

    render(<AdminSystemView data={ADMIN_DEMO_FIXTURE} />);
    expect(screen.getByRole("heading", { name: "Backup checkpoint" })).toBeVisible();
    expect(screen.getByText("Collector service")).toBeVisible();
  });
});
