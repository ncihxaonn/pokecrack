import React from "react";
import { readFileSync } from "node:fs";
import path from "node:path";
import { cleanup, render, screen } from "@testing-library/react";
import { afterEach, describe, expect, it } from "vitest";

import { BRAND } from "@/config/brand";
import {
  BatchDetailView,
  BatchesView,
  MethodologyView,
  RegionDetailView,
  RegionsView,
  RetailerDetailView,
  RetailersView,
  SetDetailView,
  SetsView,
  SourcesView,
} from "@/components/dashboard/public-views";
import { ObservationStats, PublicUnavailable } from "@/components/ui/dashboard-ui";
import { DEMO_PUBLIC_DATA } from "@/data/demo";
import { mergePublicSocialDiscovery } from "@/data/social-discovery";
import type { PublicDashboardData } from "@/data/types";
import { filterAndSortSets } from "./_lib/sets-query";

afterEach(cleanup);

describe("public route behavior", () => {
  it("filters sets case-insensitively and keeps withheld rates last", () => {
    expect(filterAndSortSets(DEMO_PUBLIC_DATA.sets, "TWILIGHT", "name").map((set) => set.slug)).toEqual(["twilight-masquerade"]);
    const byRate = filterAndSortSets(DEMO_PUBLIC_DATA.sets, "", "rate");
    expect(byRate.at(-1)?.hitRate).toBeNull();
    expect(byRate[0]?.slug).toBe("surging-sparks");
  });

  it("renders explicit live-unavailable and empty results without a demo substitution", () => {
    const { unmount } = render(<PublicUnavailable title="Set data is unavailable" message="Live aggregate data is currently unavailable. Demo fixtures were not substituted." code="upstream-unavailable" />);
    expect(screen.getByText(/Demo fixtures were not substituted/)).toBeVisible();
    expect(screen.queryByText(BRAND.demoNotice)).not.toBeInTheDocument();
    unmount();

    render(<SetsView data={{ ...DEMO_PUBLIC_DATA, sets: [] }} sets={[]} query="missing" sort="packs" synthetic />);
    expect(screen.getByText("No published sets match this search.")).toBeVisible();
  });

  it("uses the exact individual disclaimer on every relevant list and detail view", () => {
    const set = DEMO_PUBLIC_DATA.sets[0]!;
    const region = DEMO_PUBLIC_DATA.regions[0]!;
    const retailer = DEMO_PUBLIC_DATA.retailers[0]!;
    const batch = DEMO_PUBLIC_DATA.batches[0]!;
    const views = [
      <SetsView key="sets" data={DEMO_PUBLIC_DATA} sets={DEMO_PUBLIC_DATA.sets} query="" sort="packs" synthetic />,
      <SetDetailView key="set" data={DEMO_PUBLIC_DATA} set={set} synthetic />,
      <RegionsView key="regions" data={DEMO_PUBLIC_DATA} synthetic />,
      <RegionDetailView key="region" data={DEMO_PUBLIC_DATA} region={region} synthetic />,
      <RetailersView key="retailers" data={DEMO_PUBLIC_DATA} synthetic />,
      <RetailerDetailView key="retailer" data={DEMO_PUBLIC_DATA} retailer={retailer} synthetic />,
      <BatchesView key="batches" data={DEMO_PUBLIC_DATA} synthetic />,
      <BatchDetailView key="batch" data={DEMO_PUBLIC_DATA} batch={batch} synthetic />,
    ];
    for (const view of views) {
      const rendered = render(view);
      expect(screen.getByText(BRAND.individualPackDisclaimer)).toBeVisible();
      rendered.unmount();
    }
    const batchList = render(<BatchesView data={DEMO_PUBLIC_DATA} synthetic />);
    expect(screen.getByText(BRAND.batchDisclaimer)).toBeVisible();
    batchList.unmount();
    render(<BatchDetailView data={DEMO_PUBLIC_DATA} batch={batch} synthetic />);
    expect(screen.getByText(BRAND.batchDisclaimer)).toBeVisible();
  });

  it("places the batch-detail disclaimer before the primary page heading", () => {
    render(<BatchDetailView data={DEMO_PUBLIC_DATA} batch={DEMO_PUBLIC_DATA.batches[0]!} synthetic />);

    const disclaimer = screen.getByLabelText("Observation disclaimer");
    const heading = screen.getByRole("heading", { level: 1 });
    expect(disclaimer.compareDocumentPosition(heading) & Node.DOCUMENT_POSITION_FOLLOWING).not.toBe(0);
  });

  it("shows baseline, posterior, and independent-source context with observed rates", () => {
    render(<ObservationStats metric={DEMO_PUBLIC_DATA.sets[0]!} />);

    expect(screen.getByText("Independent sources")).toBeVisible();
    expect(screen.getByText("Baseline rate")).toBeVisible();
    expect(screen.getByText("Posterior mean")).toBeVisible();
  });

  it("covers the complete methodology and explicit source boundaries", () => {
    const { unmount } = render(<MethodologyView data={DEMO_PUBLIC_DATA} synthetic />);
    for (const phrase of ["AI Extractor", "independent AI Validator", "Dedup and cross-post checks", "Statistics eligibility", "Empirical Bayes interval", "90% credible interval", "descriptive observed sample rate at any sample size", "Social selection bias", "Regional correlation does not establish causation", "Retailer inventory or attribution is not pull evidence", "Version and update frequency"]) {
      expect(screen.getByText(new RegExp(phrase, "i"))).toBeVisible();
    }
    unmount();

    render(<SourcesView data={DEMO_PUBLIC_DATA} synthetic />);
    for (const name of ["Official APIs", "RSS", "Sitemaps", "Public JSON", "Policy-approved public pages", "Authenticated OpenCLI adapters", "Admin CSV/JSONL imports", "Authorized media"]) expect(screen.getByRole("heading", { name })).toBeVisible();
    expect(screen.getByText(/No login or CAPTCHA bypass/)).toBeVisible();
    expect(screen.getByText(/No proxy pools/)).toBeVisible();
    expect(screen.getByText(/No long-term full third-party video retention/)).toBeVisible();
    for (const link of screen.getAllByRole("link", { name: /Source reference/ })) {
      expect(link).toHaveAttribute("target", "_blank");
      expect(link).toHaveAttribute("rel", "noopener noreferrer");
    }
  });

  it("labels reviewed source coverage as denominator volume on the source page", () => {
    const source = DEMO_PUBLIC_DATA.sources[0]!;
    const data = {
      ...DEMO_PUBLIC_DATA,
      sources: [
        {
          ...source,
          id: "reviewed-opening-study",
          name: "Reviewed opening study",
          kind: "community" as const,
          coverage: {
            packsObserved: 55,
            countriesObserved: 1,
            completeOpenings: 1,
          },
        },
      ],
    } satisfies PublicDashboardData;

    render(<SourcesView data={data} synthetic={false} />);

    expect(screen.getByText("Reviewed opening-sample facts")).toBeVisible();
    expect(screen.getByText("No exact normalized numerator")).toBeVisible();
    expect(screen.getByText("Observed packs")).toBeVisible();
    expect(screen.getByText("Attributed coverage buckets")).toBeVisible();
    expect(screen.getByText("Complete openings")).toBeVisible();
  });

  it("does not render accidental coverage metadata on a social source", () => {
    const source = DEMO_PUBLIC_DATA.sources.find((item) => item.kind === "social")!;
    const data = {
      ...DEMO_PUBLIC_DATA,
      sources: [{
        ...source,
        coverage: {
          packsObserved: 55,
          countriesObserved: 1,
          completeOpenings: 1,
        },
      }],
    } satisfies PublicDashboardData;

    render(<SourcesView data={data} synthetic={false} />);

    expect(screen.queryByText("Coverage")).not.toBeInTheDocument();
    expect(screen.queryByText("Observed packs")).not.toBeInTheDocument();
  });

  it("renders Mastodon only from the safe activity-only source projection", () => {
    const data = mergePublicSocialDiscovery(DEMO_PUBLIC_DATA, {
      schemaVersion: "3.0.0",
      sources: [
        {
          id: "bluesky_jetstream",
          name: "Bluesky Jetstream discovery",
          kind: "social",
          access: "public",
          status: "operational",
          lastCollectedAt: "2026-08-30T10:45:00Z",
          url: "https://bsky.network/docs/jetstream/",
          note: "Public activity discovery only.",
        },
        {
          id: "nostr_multi_relay",
          name: "Nostr multi-relay discovery",
          kind: "social",
          access: "public",
          status: "operational",
          lastCollectedAt: "2026-08-31T02:15:00Z",
          url: "https://github.com/nostr-protocol/nips/blob/master/01.md",
          note: "Public activity discovery only.",
        },
        {
          id: "mastodon_public_hashtag",
          name: "Mastodon public hashtag discovery",
          kind: "social",
          access: "public",
          status: "delayed",
          lastCollectedAt: null,
          url: "https://docs.joinmastodon.org/methods/timelines/",
          note: "Public hashtag activity discovery only; never opening evidence or a pull-rate denominator.",
        },
      ],
    });

    render(<SourcesView data={data as typeof DEMO_PUBLIC_DATA} synthetic />);
    expect(screen.getByRole("heading", { name: "Mastodon public hashtag discovery" })).toBeVisible();
    expect(screen.getByText(/never opening evidence or a pull-rate denominator/)).toBeVisible();
    expect(
      screen
        .getAllByRole("link", { name: /Source reference/ })
        .find((link) => link.getAttribute("href")?.includes("joinmastodon.org")),
    ).toHaveAttribute("href", "https://docs.joinmastodon.org/methods/timelines/");
  });

  it("keeps dynamic detail misses wired to notFound and provides a dynamic ECharts enhancement with table fallback", () => {
    const detailPages = ["sets/[slug]/page.tsx", "regions/[slug]/page.tsx", "retailers/[slug]/page.tsx", "batches/[code]/page.tsx"];
    for (const page of detailPages) expect(readFileSync(path.resolve(process.cwd(), "src/app", page), "utf8"), page).toContain("notFound()");
    const chart = readFileSync(path.resolve(process.cwd(), "src/components/charts/trend-chart.tsx"), "utf8");
    expect(chart).toContain('"use client"');
    expect(chart).toContain('import("echarts")');
    expect(chart).toContain("tooltip");
    expect(chart).toContain("prefers-reduced-motion: reduce");
    expect(readFileSync(path.resolve(process.cwd(), "src/components/dashboard/home-view.tsx"), "utf8")).toContain("Observed trend values");
  });
});
