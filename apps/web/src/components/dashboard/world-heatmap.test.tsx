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
    expect(screen.getByRole("img", { name: "Baseline delta across the world" })).toHaveAttribute(
      "preserveAspectRatio",
      "xMidYMid meet",
    );
    expect(screen.getByRole("region", { name: "Exact global country values" })).toBeVisible();
    expect(screen.getByRole("cell", { name: "Brazil BR" })).toBeVisible();
    expect(screen.getAllByText("Withheld").length).toBeGreaterThan(0);
    expect(screen.getByText(/not a global independent-source count/i)).toBeVisible();
  });

  it("highlights the seven expanded collection countries without inventing observations", () => {
    const { container } = render(
      <WorldHeatmap
        cells={DEMO_PUBLIC_DATA.mapCells}
        coverageSummary={DEMO_PUBLIC_DATA.summary.globalCoverage}
        observations={DEMO_PUBLIC_DATA.observations}
      />,
    );

    const focusList = screen.getByRole("list", {
      name: "Countries in the expanded collection focus",
    });
    for (const country of GLOBAL_FOCUS_COUNTRIES) {
      expect(within(focusList).getByText(country.countryName)).toBeVisible();
    }
    expect(within(focusList).getByText("CN · Awaiting observations")).toBeVisible();
    expect(within(focusList).getByText("MX · Awaiting observations")).toBeVisible();
    expect(within(focusList).getByText("BR · Sample observed")).toBeVisible();

    const focusShapes = container.querySelectorAll('[data-focus-country="true"]');
    expect(focusShapes).toHaveLength(7);
    expect(container.querySelector('[data-country-code="CN"]'))
      .toHaveAttribute("fill", WORLD_MAP_PALETTE.noData);
    const brazilShape = container.querySelector('[data-country-code="BR"]');
    expect(brazilShape).toHaveAttribute("data-focus-country", "true");
    expect(brazilShape?.getAttribute("fill")).toMatch(/^url\(#world-withheld-/);
    expect(screen.getByRole("region", { name: "Exact global country values" }))
      .not.toHaveTextContent("China CN");
  });

  it.each(GLOBAL_FOCUS_COUNTRIES)(
    "keeps $countryName mapped and honest before and after observations arrive",
    ({ countryCode, countryName }) => {
      const expectedGeometryName = countryCode === "CN"
        ? "People's Republic of China"
        : countryName;
      expect(
        mapData.countries.filter((country) => country.countryCode === countryCode),
      ).toEqual([
        expect.objectContaining({
          countryCode,
          countryName: expectedGeometryName,
          path: expect.stringMatching(/^M/),
        }),
      ]);

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
      expect(unobservedShape).toHaveAttribute("data-focus-country", "true");
      expect(unobservedShape).toHaveAttribute("fill", WORLD_MAP_PALETTE.noData);
      expect(
        within(screen.getByRole("list", {
          name: "Countries in the expanded collection focus",
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
      expect(withheldShape).toHaveAttribute("data-focus-country", "true");
      expect(withheldShape?.getAttribute("fill")).toMatch(/^url\(#world-withheld-/);
      expect(
        within(screen.getByRole("list", {
          name: "Countries in the expanded collection focus",
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
      expect(observedShape).toHaveAttribute("data-focus-country", "true");
      expect(observedShape).toHaveAttribute(
        "fill",
        getWorldMapFill(publishedCell.packsObserved, "coverage"),
      );
      expect(
        within(screen.getByRole("list", {
          name: "Countries in the expanded collection focus",
        })).getByText(`${countryCode} · Rate published`),
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
    expect(screen.getByRole("img", { name: "Observed rate across the world" })).toBeVisible();
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
    expect(screen.queryByText("No country-level rates published yet")).not.toBeInTheDocument();
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

    expect(screen.getByText("Publication pending")).toBeVisible();
    expect(screen.getByText(/met the evidence threshold and await reviewed publication/i)).toBeVisible();
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
    expect(screen.getByText("No verified country observations are published yet.")).toBeVisible();
    expect(screen.getByRole("img", { name: "Observed pack coverage across the world" })).toHaveAccessibleDescription(
      /7 countries have gold outlines as collection targets only/i,
    );
  });
});
