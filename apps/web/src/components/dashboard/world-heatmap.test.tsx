import React from "react";
import { fireEvent, render, screen, within } from "@testing-library/react";
import { describe, expect, it } from "vitest";

import { DEMO_PUBLIC_DATA } from "@/data/demo";
import mapData from "@/data/world-map-110m.json";
import {
  buildWorldHeatRows,
  GLOBAL_FOCUS_COUNTRIES,
  getWorldMapFill,
  WORLD_MAP_PALETTE,
  WorldHeatmap,
} from "./world-heatmap";

const syntheticJapanDataVersion = "ja · M3 · ムニキスゼロ · booster box";

function relativeLuminance(hex: string) {
  const channels = [1, 3, 5].map((offset) => {
    const value = Number.parseInt(hex.slice(offset, offset + 2), 16) / 255;
    return value <= 0.04045
      ? value / 12.92
      : ((value + 0.055) / 1.055) ** 2.4;
  });
  return (channels[0] ?? 0) * 0.2126
    + (channels[1] ?? 0) * 0.7152
    + (channels[2] ?? 0) * 0.0722;
}

function contrastRatio(first: string, second: string) {
  const firstLuminance = relativeLuminance(first);
  const secondLuminance = relativeLuminance(second);
  return (Math.max(firstLuminance, secondLuminance) + 0.05)
    / (Math.min(firstLuminance, secondLuminance) + 0.05);
}

describe("WorldHeatmap", () => {
  it("renders a global fixed-scale map with exact accessible values", () => {
    render(
      <WorldHeatmap
        cells={DEMO_PUBLIC_DATA.mapCells}
        coverageSummary={DEMO_PUBLIC_DATA.summary.globalCoverage}
        observations={DEMO_PUBLIC_DATA.observations}
      />,
    );

    expect(screen.getByRole("heading", { name: "Worldwide qualifying-hit map" })).toBeVisible();
    expect(screen.getByRole("img", { name: "Observed sample rate across the world" })).toHaveAttribute(
      "preserveAspectRatio",
      "xMidYMid meet",
    );
    expect(screen.getByRole("region", { name: "Exact country and product-market coverage values" })).toBeVisible();
    expect(screen.getByRole("cell", { name: "Brazil BR · Country" })).toBeVisible();
    expect(screen.getAllByText("Withheld").length).toBeGreaterThan(0);
    expect(screen.getByText(/not a global independent-source count/i)).toBeVisible();
  });

  it("renders a synthetic localized UI fixture without publishing a Japan rate", () => {
    const syntheticJapan = {
      ...DEMO_PUBLIC_DATA.mapCells.find((cell) => cell.countryCode === "BR")!,
      countryCode: "JP",
      countryName: "Japan",
      dataVersions: [syntheticJapanDataVersion],
      collectionClass: "coverage_only" as const,
      coverageAttributionBases: ["product_market"] as const,
      packsObserved: 30,
      openings: 1,
      independentSources: 1,
      state: "insufficient" as const,
      sampleNote: "Synthetic parser/UI fixture only; no published evidence or rate.",
    };
    render(
      <WorldHeatmap
        cells={[syntheticJapan]}
        coverageSummary="Synthetic parser/UI fixture only; this is not published evidence."
        initialMetric="coverage"
        observations={{
          ...DEMO_PUBLIC_DATA.observations,
          status: "collecting",
          observedPacks: 30,
          completeOpenings: 1,
          sourceCountryContributions: 1,
          countriesObserved: 1,
          countriesWithPublishedRate: 0,
        }}
      />,
    );

    expect(screen.getByRole("columnheader", { name: "Data version" })).toBeVisible();
    const version = screen.getByText(syntheticJapanDataVersion);
    expect(version).toBeVisible();
    expect(version).toHaveAttribute("dir", "auto");
    expect(version).toHaveAttribute("lang", "ja");
    expect(version.closest("td")).toHaveAttribute("data-label", "Data version");
    const japanRow = screen.getByRole("row", { name: /Japan JP/ });
    expect(japanRow.querySelector('td[data-label="Sample rate"]')).toHaveTextContent("Withheld");
    expect(japanRow.querySelector('td[data-label="Hits / rate packs"]')).toHaveTextContent("Not available");
    expect(japanRow.querySelector('td[data-label="Baseline"]')).toHaveTextContent("Withheld");
    expect(japanRow.querySelector('td[data-label="Delta"]')).toHaveTextContent("N/A");
    expect(japanRow.querySelector('td[data-label="Status"]')).toHaveTextContent("No exact numerator");
    expect(within(japanRow).queryByText(/\d+(?:\.\d+)?%/)).not.toBeInTheDocument();
    expect(screen.getByText("JP · Sample observed")).toBeVisible();
    expect(screen.getByText("JP · Product market")).toBeVisible();
  });

  it("renders the five real Americas coverage rows with exact data versions", () => {
    const template = DEMO_PUBLIC_DATA.mapCells.find((cell) => cell.countryCode === "BR")!;
    const definitions = [
      ["CR", "Costa Rica", 4, "und · swsh6 · Chilling Reign · build and battle"],
      ["CO", "Colombia", 2, "und · me03 · Perfect Order · all products"],
      ["EC", "Ecuador", 20, "und · sm12 · Cosmic Eclipse · all products"],
      ["PE", "Peru", 36, "und · swsh11 · Lost Origin · booster box"],
      ["UY", "Uruguay", 36, "und · swsh12 · Silver Tempest · booster box"],
    ] as const;
    const cells = definitions.map(([countryCode, countryName, packsObserved, version]) => ({
      ...template,
      countryCode,
      countryName,
      dataVersions: [version],
      collectionClass: "coverage_only" as const,
      coverageAttributionBases: ["publisher_country"] as const,
      periodStart: "2021-06-06",
      periodEnd: "2026-09-05",
      packsObserved,
      openings: 1,
      independentSources: 1,
      ratePacksObserved: undefined,
      qualifyingHitPacks: undefined,
      baselineRate: null,
      hitRate: null,
      posteriorMean: null,
      credibleInterval: null,
      deltaFromBaseline: null,
      state: "insufficient" as const,
      sampleNote: "Reviewed denominator-only coverage; no exact normalized numerator.",
      updatedAt: "2026-09-05T00:00:00Z",
    }));

    const { container } = render(
      <WorldHeatmap
        cells={cells}
        coverageSummary="Five reviewed Americas coverage buckets."
        initialMetric="coverage"
        observations={{
          ...DEMO_PUBLIC_DATA.observations,
          status: "collecting",
          period: { start: "2021-06-06", end: "2026-09-05" },
          observedPacks: 98,
          completeOpenings: 5,
          sourceCountryContributions: 5,
          countriesObserved: 5,
          countriesWithPublishedRate: 0,
        }}
      />,
    );

    for (const [countryCode, countryName, , version] of definitions) {
      expect(screen.getByRole("row", { name: new RegExp(`${countryName} ${countryCode}`) }))
        .toHaveTextContent(version);
      expect(container.querySelector(`[data-country-code="${countryCode}"]`))
        .not.toHaveAttribute("fill", WORLD_MAP_PALETTE.noData);
    }
    expect(screen.getByText("06 Jun 2021 - 05 Sep 2026")).toBeVisible();
  });

  it("renders a clear fallback for legacy cells without data versions", () => {
    const legacy = DEMO_PUBLIC_DATA.mapCells.find((cell) => cell.countryCode === "BR")!;
    render(
      <WorldHeatmap
        cells={[legacy]}
        coverageSummary="One legacy country sample."
        initialMetric="coverage"
        observations={{
          ...DEMO_PUBLIC_DATA.observations,
          status: "collecting",
          observedPacks: legacy.packsObserved,
          completeOpenings: legacy.openings,
          sourceCountryContributions: legacy.independentSources,
          countriesObserved: 1,
          countriesWithPublishedRate: 0,
        }}
      />,
    );

    const fallback = screen.getByText("Not provided");
    expect(fallback).toBeVisible();
    expect(fallback.closest("td")).toHaveAttribute("data-label", "Data version");
  });

  it("highlights the twenty-six expanded collection countries without inventing observations", () => {
    const { container } = render(
      <WorldHeatmap
        cells={DEMO_PUBLIC_DATA.mapCells}
        coverageSummary={DEMO_PUBLIC_DATA.summary.globalCoverage}
        observations={DEMO_PUBLIC_DATA.observations}
      />,
    );

    const focusList = screen.getByRole("list", {
      name: "Countries and product markets in the expanded collection focus",
    });
    for (const country of GLOBAL_FOCUS_COUNTRIES) {
      expect(within(focusList).getByText(country.countryName)).toBeVisible();
    }
    expect(focusList.querySelectorAll("li")).toHaveLength(26);
    expect(within(focusList).getByText("CN · Awaiting observations")).toBeVisible();
    expect(within(focusList).getByText("MX · Awaiting observations")).toBeVisible();
    expect(within(focusList).getByText("BR · Sample observed")).toBeVisible();
    for (const countryCode of [
      "PR",
      "GT",
      "PA",
      "CR",
      "CO",
      "EC",
      "PE",
      "AR",
      "CL",
      "UY",
      "KR",
      "TW",
      "HK",
      "TH",
      "ID",
      "MY",
      "PH",
      "VN",
      "IN",
    ]) {
      expect(within(focusList).getByText(`${countryCode} · Awaiting observations`)).toBeVisible();
    }

    const focusShapes = container.querySelectorAll('[data-focus-country="true"]');
    expect(focusShapes).toHaveLength(25);
    expect(within(focusList).getByText("List/table only · no separate map geometry")).toBeVisible();
    expect(container.querySelector('[data-country-code="CN"]'))
      .toHaveAttribute("fill", WORLD_MAP_PALETTE.noData);
    const brazilShape = container.querySelector('[data-country-code="BR"]');
    expect(brazilShape).toHaveAttribute("data-focus-country", "true");
    expect(brazilShape?.getAttribute("fill")).toMatch(/^url\(#world-withheld-/);
    expect(screen.getByRole("region", { name: "Exact country and product-market coverage values" }))
      .not.toHaveTextContent("China CN");
  });

  it.each(GLOBAL_FOCUS_COUNTRIES)(
    "keeps $countryName mapped and honest before and after observations arrive",
    ({ countryCode, countryName }) => {
      const expectedGeometryName = countryCode === "CN"
        ? "People's Republic of China"
        : countryName;
      const mapCountries = mapData.countries.filter((country) => country.countryCode === countryCode);
      const tinyCountries = mapData.tinyCountries.filter(
        (country) => country.countryCode === countryCode,
      );
      const geometryCount = mapCountries.length + tinyCountries.length;
      if (geometryCount === 0) {
        expect(countryCode).toBe("HK");
      } else {
        expect(geometryCount).toBe(1);
        if (mapCountries.length === 1) {
          expect(mapCountries).toEqual([
            expect.objectContaining({
              countryCode,
              countryName: expectedGeometryName,
              path: expect.stringMatching(/^M/),
            }),
          ]);
        }
      }

      const emptyRender = render(
        <WorldHeatmap
          cells={[]}
          coverageSummary="No verified country observations yet."
          initialMetric="coverage"
          observations={{
            ...DEMO_PUBLIC_DATA.observations,
            status: "empty",
            period: null,
            observedPacks: 0,
            completeOpenings: 0,
            sourceCountryContributions: 0,
            countriesObserved: 0,
            countriesWithPublishedRate: 0,
            asOf: null,
            methodologyVersion: null,
          }}
        />,
      );
      const unobservedShape = emptyRender.container.querySelector(
        `[data-country-code="${countryCode}"]`,
      );
      if (geometryCount === 0) {
        expect(unobservedShape).toBeNull();
      } else {
        expect(unobservedShape).toHaveAttribute("data-focus-country", "true");
        expect(unobservedShape).toHaveAttribute("fill", WORLD_MAP_PALETTE.noData);
      }
      expect(
        within(screen.getByRole("list", {
          name: "Countries and product markets in the expanded collection focus",
        })).getByText(`${countryCode} · Awaiting observations`),
      ).toBeVisible();
      emptyRender.unmount();

      const withheldTemplate = DEMO_PUBLIC_DATA.mapCells.find(
        (cell) => cell.countryCode === "BR",
      )!;
      const withheldCell = {
        ...withheldTemplate,
        countryCode,
        countryName,
      };
      const withheldRender = render(
        <WorldHeatmap
          cells={[withheldCell]}
          coverageSummary="One observed country sample with its rate withheld."
          initialMetric="rate"
          observations={{
            ...DEMO_PUBLIC_DATA.observations,
            status: "collecting",
            observedPacks: withheldCell.packsObserved,
            completeOpenings: withheldCell.openings,
            sourceCountryContributions: withheldCell.independentSources,
            countriesObserved: 1,
            countriesWithPublishedRate: 0,
          }}
        />,
      );
      const withheldShape = withheldRender.container.querySelector(
        `[data-country-code="${countryCode}"]`,
      );
      if (geometryCount === 0) {
        expect(withheldShape).toBeNull();
      } else {
        expect(withheldShape).toHaveAttribute("data-focus-country", "true");
        expect(withheldShape?.getAttribute("fill")).toMatch(/^url\(#world-withheld-/);
      }
      expect(
        within(screen.getByRole("list", {
          name: "Countries and product markets in the expanded collection focus",
        })).getByText(`${countryCode} · Sample observed`),
      ).toBeVisible();
      withheldRender.unmount();

      const publishedTemplate = DEMO_PUBLIC_DATA.mapCells.find(
        (cell) => cell.hitRate !== null,
      )!;
      const publishedCell = {
        ...publishedTemplate,
        countryCode,
        countryName,
      };
      const observedRender = render(
        <WorldHeatmap
          cells={[publishedCell]}
          coverageSummary="One verified country sample."
          initialMetric="coverage"
          observations={{
            ...DEMO_PUBLIC_DATA.observations,
            observedPacks: publishedCell.packsObserved,
            completeOpenings: publishedCell.openings,
            sourceCountryContributions: publishedCell.independentSources,
            countriesObserved: 1,
            countriesWithPublishedRate: 1,
          }}
        />,
      );
      const observedShape = observedRender.container.querySelector(
        `[data-country-code="${countryCode}"]`,
      );
      if (geometryCount === 0) {
        expect(observedShape).toBeNull();
      } else {
        expect(observedShape).toHaveAttribute("data-focus-country", "true");
        expect(observedShape).toHaveAttribute(
          "fill",
          getWorldMapFill(publishedCell.packsObserved, "coverage"),
        );
      }
      expect(
        within(screen.getByRole("list", {
          name: "Countries and product markets in the expanded collection focus",
        })).getByText(`${countryCode} · Sample rate available`),
      ).toBeVisible();
    },
  );

  it("switches between delta and rate without snapshot-relative normalization", () => {
    render(
      <WorldHeatmap
        cells={DEMO_PUBLIC_DATA.mapCells}
        coverageSummary={DEMO_PUBLIC_DATA.summary.globalCoverage}
        observations={DEMO_PUBLIC_DATA.observations}
      />,
    );

    fireEvent.click(screen.getByRole("button", { name: "Observed rate" }));
    expect(screen.getByRole("button", { name: "Observed rate" })).toHaveAttribute("aria-pressed", "true");
    expect(screen.getByRole("img", { name: "Observed sample rate across the world" })).toBeVisible();
    expect(screen.getByText("15%")).toBeVisible();

    expect(getWorldMapFill(-1, "delta")).toBe(getWorldMapFill(-0.05, "delta"));
    expect(getWorldMapFill(1, "delta")).toBe(getWorldMapFill(0.05, "delta"));
    expect(getWorldMapFill(1, "rate")).toBe(getWorldMapFill(0.3, "rate"));
  });

  it("uses a fixed pack-volume scale for coverage without publishing a rate", () => {
    const withheld = DEMO_PUBLIC_DATA.mapCells.find((cell) => cell.countryCode === "BR")!;
    const rows = buildWorldHeatRows([withheld], "coverage");

    expect(rows[0]).toMatchObject({
      metricValue: withheld.packsObserved,
      status: "observed",
    });
    expect(rows[0]?.fill).not.toBe("withheld");
    expect(getWorldMapFill(-1, "coverage")).toBe(getWorldMapFill(0, "coverage"));
    expect(getWorldMapFill(5_000, "coverage")).toBe(getWorldMapFill(1_500, "coverage"));
    expect(getWorldMapFill(0, "coverage")).toBe(WORLD_MAP_PALETTE.quantitativeLow);
    expect(getWorldMapFill(1_500, "coverage")).toBe(WORLD_MAP_PALETTE.quantitativeHigh);

    render(
      <WorldHeatmap
        cells={[withheld]}
        coverageSummary="One reviewed country sample."
        initialMetric="coverage"
        observations={{
          ...DEMO_PUBLIC_DATA.observations,
          countriesObserved: 1,
          countriesWithPublishedRate: 0,
        }}
      />,
    );

    expect(screen.getByRole("heading", { name: "Worldwide evidence coverage" })).toBeVisible();
    expect(screen.getByRole("img", { name: "Observed pack coverage across the world" })).toHaveAccessibleDescription(
      /not a hit rate or representative demand/i,
    );
    expect(screen.getByText("Observed pack sample uses scale")).toBeVisible();
    expect(screen.getByRole("group", { name: "Observed pack coverage map legend" }))
      .toHaveTextContent(/0 packs.*750.*≥ 1,500/);
    expect(screen.queryByText("No attributed bucket rates published yet")).not.toBeInTheDocument();
  });

  it("colours and labels an exact low-sample observed rate without inference", () => {
    const rawSample = {
      ...DEMO_PUBLIC_DATA.mapCells.find((cell) => cell.countryCode === "BR")!,
      packsObserved: 91,
      openings: 2,
      independentSources: 2,
      ratePacksObserved: 91,
      qualifyingHitPacks: 2,
      hitRate: 2 / 91,
      baselineRate: null,
      posteriorMean: null,
      credibleInterval: null,
      deltaFromBaseline: null,
      state: "insufficient" as const,
      sampleNote: "Direct observed sample: 2 qualifying-hit packs among 91.",
    };
    const { container } = render(
      <WorldHeatmap
        cells={[rawSample]}
        coverageSummary="One exact observed sample rate."
        initialMetric="rate"
        observations={{
          ...DEMO_PUBLIC_DATA.observations,
          status: "published",
          observedPacks: 91,
          completeOpenings: 2,
          sourceCountryContributions: 2,
          countriesObserved: 1,
          countriesWithPublishedRate: 1,
        }}
      />,
    );

    expect(container.querySelector('[data-country-code="BR"]')).toHaveAttribute(
      "fill",
      getWorldMapFill(2 / 91, "rate"),
    );
    const brazilRow = screen.getByRole("row", { name: /Brazil BR/ });
    expect(brazilRow.querySelector('td[data-label="Hits / rate packs"]')).toHaveTextContent("2 / 91");
    expect(brazilRow.querySelector('td[data-label="Sample rate"]')).toHaveTextContent("2.2%");
    expect(brazilRow.querySelector('td[data-label="Baseline"]')).toHaveTextContent("Withheld");
    expect(brazilRow.querySelector('td[data-label="Delta"]')).toHaveTextContent("N/A");
    expect(brazilRow.querySelector('td[data-label="Status"]')).toHaveTextContent("Observed sample");
    expect(screen.getByText("BR · Sample rate available")).toBeVisible();
    expect(screen.getByText("Observed sample rate uses scale")).toBeVisible();

    fireEvent.click(screen.getByRole("button", { name: "Baseline delta" }));
    expect(screen.getByText("No baseline deltas published yet")).toBeVisible();
    expect(screen.getByRole("img", { name: "Baseline delta across the world" }))
      .toHaveAccessibleDescription(/0 have a published baseline delta/i);
  });

  it("keeps low-volume observations vivid while preserving a distinct no-data state", () => {
    expect(WORLD_MAP_PALETTE).toMatchObject({
      background: "#f8fafc",
      noData: "#dce3ed",
      boundary: "#7c8b9f",
      quantitativeLow: "#2563eb",
      quantitativeMid: "#1d4ed8",
      quantitativeHigh: "#172554",
      withheldBase: "#2563eb",
      withheldStripe: "#dbeafe",
      focus: "#9b6a12",
      labelAccent: "#075985",
    });
    expect(getWorldMapFill(10, "coverage")).not.toBe(WORLD_MAP_PALETTE.noData);
    // Neutral countries use a light fill with a contrasting boundary on the light atlas.
    expect(contrastRatio(WORLD_MAP_PALETTE.boundary, WORLD_MAP_PALETTE.background))
      .toBeGreaterThanOrEqual(3);
    expect(contrastRatio(WORLD_MAP_PALETTE.quantitativeLow, WORLD_MAP_PALETTE.noData))
      .toBeGreaterThanOrEqual(3);
    expect(contrastRatio(WORLD_MAP_PALETTE.withheldBase, WORLD_MAP_PALETTE.background))
      .toBeGreaterThanOrEqual(3);
    expect(contrastRatio(WORLD_MAP_PALETTE.labelAccent, "#f3f6f3"))
      .toBeGreaterThanOrEqual(4.5);
  });

  it("records the selected metric in the URL", () => {
    window.history.replaceState(null, "", "/?source=qa#map");
    render(
      <WorldHeatmap
        cells={DEMO_PUBLIC_DATA.mapCells}
        coverageSummary={DEMO_PUBLIC_DATA.summary.globalCoverage}
        observations={DEMO_PUBLIC_DATA.observations}
      />,
    );

    fireEvent.click(screen.getByRole("button", { name: "Pack coverage" }));
    expect(window.location.search).toBe("?source=qa&metric=coverage");
    expect(window.location.hash).toBe("#map");
  });

  it("sorts exact rows alphabetically and preserves withheld countries", () => {
    const rows = buildWorldHeatRows(DEMO_PUBLIC_DATA.mapCells, "delta");
    expect(rows.map((row) => row.cell.countryName)).toEqual([
      "Australia",
      "Brazil",
      "Germany",
      "Japan",
      "United Kingdom",
      "United States",
    ]);
    expect(rows.find((row) => row.cell.countryCode === "BR")?.status).toBe("withheld");
  });

  it("distinguishes a threshold-sufficient row awaiting reviewed publication", () => {
    const pending = {
      ...DEMO_PUBLIC_DATA.mapCells.find((cell) => cell.countryCode === "BR")!,
      independentSources: 3,
      state: "pending" as const,
      sampleNote: "Evidence threshold met; reviewed publication pending.",
    };
    render(
      <WorldHeatmap
        cells={[pending]}
        coverageSummary="One country awaits reviewed publication."
        initialMetric="delta"
        observations={{
          ...DEMO_PUBLIC_DATA.observations,
          status: "collecting",
          observedPacks: pending.packsObserved,
          completeOpenings: pending.openings,
          sourceCountryContributions: pending.independentSources,
          countriesObserved: 1,
          countriesWithPublishedRate: 0,
        }}
      />,
    );

    expect(screen.getByText("Inference pending")).toBeVisible();
    expect(screen.getByText("BR · Inference pending")).toBeVisible();
    expect(screen.queryByText("BR · Sample observed")).not.toBeInTheDocument();
    expect(screen.getByText(/has no published inference yet/i)).toBeVisible();
  });

  it("shows an honest neutral empty state", () => {
    render(
      <WorldHeatmap
        cells={[]}
        coverageSummary="No verified country-level opening samples are published yet."
        observations={{
          ...DEMO_PUBLIC_DATA.observations,
          status: "empty",
          period: null,
          observedPacks: 0,
          completeOpenings: 0,
          sourceCountryContributions: 0,
          countriesObserved: 0,
          countriesWithPublishedRate: 0,
          asOf: null,
          methodologyVersion: null,
        }}
      />,
    );
    expect(screen.getByText("Awaiting observations")).toBeVisible();
    expect(screen.getByText("No verified pack coverage yet")).toBeVisible();
    expect(screen.getByText("No verified country or product-market coverage is published yet.")).toBeVisible();
    expect(screen.getByRole("img", { name: "Observed pack coverage across the world" })).toHaveAccessibleDescription(
      /25 collection targets have gold outlines.*Hong Kong.*no separate geometry/i,
    );
  });
});
