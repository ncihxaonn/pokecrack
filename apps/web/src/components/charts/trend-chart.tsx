"use client";

import React, { useEffect, useRef } from "react";

import type { TrendPoint } from "@/data/types";

export function getTrendAnimationOptions(reducedMotion: boolean) {
  return {
    animation: !reducedMotion,
    animationDuration: reducedMotion ? 0 : 450,
  } as const;
}

export function TrendChart({ points }: { points: readonly TrendPoint[] }) {
  const containerRef = useRef<HTMLDivElement>(null);

  useEffect(() => {
    if (!containerRef.current || points.length === 0 || process.env.NODE_ENV === "test") return;
    let disposed = false;
    let chart: import("echarts").ECharts | undefined;
    let observer: ResizeObserver | undefined;

    void import("echarts").then((echarts) => {
      if (disposed || !containerRef.current) return;
      const reducedMotion = window.matchMedia?.("(prefers-reduced-motion: reduce)").matches ?? false;
      chart = echarts.init(containerRef.current, undefined, { renderer: "canvas" });
      chart.setOption({
        ...getTrendAnimationOptions(reducedMotion),
        backgroundColor: "transparent",
        grid: { left: 42, right: 18, top: 22, bottom: 32 },
        tooltip: {
          trigger: "axis",
          valueFormatter: (value: unknown) => typeof value === "number" ? `${(value * 100).toFixed(1)}%` : String(value),
          backgroundColor: "#ffffff",
          borderColor: "#d9dde5",
          textStyle: { color: "#171a21", fontFamily: "monospace" },
          extraCssText: "box-shadow: 0 10px 30px rgba(23,26,33,.12); border-radius: 10px;",
        },
        xAxis: {
          type: "category",
          data: points.map((point) => point.date),
          axisLabel: { color: "#667085", fontFamily: "monospace", hideOverlap: true },
          axisLine: { lineStyle: { color: "#d9dde5" } },
        },
        yAxis: {
          type: "value",
          axisLabel: { color: "#667085", formatter: (value: number) => `${Math.round(value * 100)}%` },
          splitLine: { lineStyle: { color: "#eceef2" } },
        },
        series: [
          { name: "Observed rate", type: "line", data: points.map((point) => point.observedRate), smooth: true, symbolSize: 7, lineStyle: { color: "#315efb", width: 3 }, itemStyle: { color: "#315efb", borderColor: "#ffffff", borderWidth: 2 }, areaStyle: { color: "rgba(49,94,251,.09)" } },
          { name: "Baseline", type: "line", data: points.map((point) => point.baselineRate), symbol: "none", lineStyle: { color: "#f34f91", width: 2, type: "dashed" } },
        ],
      });
      observer = new ResizeObserver(() => chart?.resize());
      observer.observe(containerRef.current);
    });

    return () => {
      disposed = true;
      observer?.disconnect();
      chart?.dispose();
    };
  }, [points]);

  if (points.length === 0) return <p className="empty-cell">No trend series is published in this snapshot.</p>;
  return <div ref={containerRef} className="echart" role="img" aria-label="Line chart of weekly observed rate and baseline; exact values follow in a table" />;
}
