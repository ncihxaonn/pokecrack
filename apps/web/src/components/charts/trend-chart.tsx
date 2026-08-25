"use client";

import React, { useEffect, useRef } from "react";

import type { TrendPoint } from "@/data/types";

export function TrendChart({ points }: { points: readonly TrendPoint[] }) {
  const containerRef = useRef<HTMLDivElement>(null);

  useEffect(() => {
    if (!containerRef.current || points.length === 0 || process.env.NODE_ENV === "test") return;
    let disposed = false;
    let chart: import("echarts").ECharts | undefined;
    let observer: ResizeObserver | undefined;

    void import("echarts").then((echarts) => {
      if (disposed || !containerRef.current) return;
      chart = echarts.init(containerRef.current, undefined, { renderer: "canvas" });
      chart.setOption({
        animationDuration: 450,
        backgroundColor: "transparent",
        grid: { left: 42, right: 18, top: 22, bottom: 32 },
        tooltip: {
          trigger: "axis",
          valueFormatter: (value: unknown) => typeof value === "number" ? `${(value * 100).toFixed(1)}%` : String(value),
          backgroundColor: "#11151a",
          borderColor: "#303944",
          textStyle: { color: "#f0f3f6", fontFamily: "monospace" },
        },
        xAxis: {
          type: "category",
          data: points.map((point) => point.date),
          axisLabel: { color: "#8d98a5", fontFamily: "monospace", hideOverlap: true },
          axisLine: { lineStyle: { color: "#303944" } },
        },
        yAxis: {
          type: "value",
          axisLabel: { color: "#8d98a5", formatter: (value: number) => `${Math.round(value * 100)}%` },
          splitLine: { lineStyle: { color: "#20262e" } },
        },
        series: [
          { name: "Observed rate", type: "line", data: points.map((point) => point.observedRate), smooth: true, symbolSize: 6, lineStyle: { color: "#a6ff4d", width: 2 }, itemStyle: { color: "#a6ff4d" }, areaStyle: { color: "rgba(166,255,77,.08)" } },
          { name: "Baseline", type: "line", data: points.map((point) => point.baselineRate), symbol: "none", lineStyle: { color: "#63d8ff", width: 1, type: "dashed" } },
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
