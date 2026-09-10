import { describe, expect, it, vi } from "vitest";

import type { DashboardResult } from "@/data/resolver";
import { DEMO_PUBLIC_DATA } from "@/data/demo";
import { DASHBOARD_CACHE_TTL_SECONDS, resolveFreshDashboard } from "./dashboard-freshness";

const cached: DashboardResult = {
  status: "unavailable", mode: "live", code: "upstream-unavailable", message: "cached",
};
const fresh: DashboardResult = { ...cached, message: "fresh" };
const now = 1_000_000;

describe("public dashboard hard cache age", () => {
  it("shows a new denominator when a cache backend keeps returning its old entry", async () => {
    // Synthetic cache fixture only; these test objects are never published.
    const before: DashboardResult = {
      status: "ready", mode: "live", synthetic: false,
      data: { ...DEMO_PUBLIC_DATA, mode: "live", observations: {
        ...DEMO_PUBLIC_DATA.observations, observedPacks: 1_159, completeOpenings: 34,
      } },
    };
    const after: DashboardResult = { ...before, data: { ...before.data, observations: {
      ...before.data.observations, observedPacks: 1_249, completeOpenings: 37,
    } } };
    const loadFresh = vi.fn().mockResolvedValue(after);
    const result = await resolveFreshDashboard({ cachedAt: 0, result: before }, loadFresh, now);
    expect(result).toBe(after);
    expect(before.data.observations.observedPacks).toBe(1_159);
    expect(loadFresh).toHaveBeenCalledOnce();
  });

  it.each([0, 59_999])("reuses a result aged %i milliseconds", async (age) => {
    const loadFresh = vi.fn().mockResolvedValue(fresh);
    expect(await resolveFreshDashboard({ cachedAt: now - age, result: cached }, loadFresh, now))
      .toBe(cached);
    expect(loadFresh).not.toHaveBeenCalled();
  });

  it.each([60_000, 120_000, 86_400_000])("awaits fresh data at age %i without relying on background refresh", async (age) => {
    const loadFresh = vi.fn().mockResolvedValue(fresh);
    expect(await resolveFreshDashboard({ cachedAt: now - age, result: cached }, loadFresh, now))
      .toBe(fresh);
    expect(loadFresh).toHaveBeenCalledOnce();
  });

  it.each([now + 1, Number.NaN, Number.POSITIVE_INFINITY])("does not trust an invalid or future cache timestamp %s", async (cachedAt) => {
    const loadFresh = vi.fn().mockResolvedValue(fresh);
    expect(await resolveFreshDashboard({ cachedAt, result: cached }, loadFresh, now)).toBe(fresh);
    expect(loadFresh).toHaveBeenCalledOnce();
  });

  it("does not replace a failed refresh with expired evidence", async () => {
    const loadFresh = vi.fn().mockRejectedValue(new Error("upstream unavailable"));
    await expect(resolveFreshDashboard({ cachedAt: 0, result: cached }, loadFresh, now))
      .rejects.toThrow("upstream unavailable");
  });

  it("keeps the one-minute budget explicit", () => {
    expect(DASHBOARD_CACHE_TTL_SECONDS).toBe(60);
  });
});
