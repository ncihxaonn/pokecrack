import { describe, expect, it, vi } from "vitest";

import { parseEnv } from "@/config/env";
import { DEMO_DATA } from "./demo";
import { resolveDashboardData } from "./resolver";

const liveEnv = parseEnv({
  DATA_MODE: "live",
  NEXT_PUBLIC_SUPABASE_URL: "https://project.supabase.co",
  NEXT_PUBLIC_SUPABASE_PUBLISHABLE_KEY: "public-key",
});

describe("resolveDashboardData", () => {
  it("serves deterministic fixtures only when DATA_MODE is demo", async () => {
    const loadLive = vi.fn();
    const result = await resolveDashboardData(parseEnv({ DATA_MODE: "demo" }), loadLive);

    expect(result).toMatchObject({ status: "ready", mode: "demo", synthetic: true });
    expect(result.status === "ready" && result.data.mode).toBe("demo");
    expect(result.status === "ready" && result.data).not.toHaveProperty("admin");
    expect(result.status === "ready" && result.data.recentActivity.every((item) => item.published)).toBe(true);
    expect(loadLive).not.toHaveBeenCalled();
  });

  it("fails closed when live mode is not configured", async () => {
    const loadLive = vi.fn();
    const result = await resolveDashboardData(parseEnv({ DATA_MODE: "live" }), loadLive);

    expect(result).toMatchObject({
      status: "unavailable",
      mode: "live",
      code: "supabase-unconfigured",
    });
    expect(result).not.toHaveProperty("data");
    expect(loadLive).not.toHaveBeenCalled();
  });

  it("does not substitute fixtures when the live provider fails", async () => {
    const result = await resolveDashboardData(liveEnv, async () => {
      throw new Error("connection details must not leak");
    });

    expect(result).toMatchObject({
      status: "unavailable",
      mode: "live",
      code: "upstream-unavailable",
    });
    expect(result.status === "unavailable" && result.message).not.toMatch(/connection details/i);
    expect(result).not.toHaveProperty("data");
  });

  it("rejects malformed live payloads", async () => {
    const result = await resolveDashboardData(liveEnv, async () => ({ mode: "live" }));

    expect(result).toMatchObject({
      status: "unavailable",
      code: "invalid-payload",
    });
  });

  it("accepts a validated aggregate-only live snapshot", async () => {
    const { admin, ...publicFixture } = DEMO_DATA;
    expect(admin).toBeDefined();
    const liveSnapshot = { ...publicFixture, mode: "live" as const };
    const result = await resolveDashboardData(liveEnv, async () => liveSnapshot);

    expect(result).toMatchObject({ status: "ready", mode: "live", synthetic: false });
    expect(result.status === "ready" && result.data.mode).toBe("live");
    expect(result.status === "ready" && result.data.recentActivity.every((item) => item.published)).toBe(true);
    expect(result.status === "ready" && result.data.recentActivity.length).toBe(
      DEMO_DATA.recentActivity.filter((item) => item.published).length,
    );
  });
});
