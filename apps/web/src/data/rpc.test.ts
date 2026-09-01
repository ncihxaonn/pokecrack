import { describe, expect, it } from "vitest";

import {
  PUBLIC_DASHBOARD_RPC,
  PUBLIC_SOCIAL_DISCOVERY_FALLBACK_RPC,
  PUBLIC_SOCIAL_DISCOVERY_RPC,
  PUBLIC_STUDY_COVERAGE_RPC,
  unwrapRpcSnapshot,
} from "./rpc";

describe("aggregate RPC adapter", () => {
  it("uses a versioned public aggregate snapshot contract", () => {
    expect(PUBLIC_DASHBOARD_RPC).toBe("get_public_dashboard_snapshot_v3");
    expect(PUBLIC_DASHBOARD_RPC).not.toMatch(/raw|ingest|observation/i);
    expect(PUBLIC_STUDY_COVERAGE_RPC).toBe("get_public_study_coverage_v1");
    expect(PUBLIC_STUDY_COVERAGE_RPC).not.toMatch(/raw|evidence|hit/i);
    expect(PUBLIC_SOCIAL_DISCOVERY_RPC).toBe("get_public_social_discovery_v3");
    expect(PUBLIC_SOCIAL_DISCOVERY_RPC).not.toBe("get_public_social_discovery_v2");
    expect(PUBLIC_SOCIAL_DISCOVERY_RPC).not.toMatch(/raw|post|cursor|candidate/i);
    expect(PUBLIC_SOCIAL_DISCOVERY_FALLBACK_RPC).toBe(
      "get_public_social_discovery_v1",
    );
    expect(PUBLIC_SOCIAL_DISCOVERY_FALLBACK_RPC).not.toMatch(
      /raw|post|cursor|candidate/i,
    );
  });

  it("returns successful RPC data and fails without leaking provider details", () => {
    expect(unwrapRpcSnapshot({ data: { mode: "live" }, error: null })).toEqual({
      mode: "live",
    });
    expect(() =>
      unwrapRpcSnapshot({
        data: null,
        error: { message: "postgres host and internal query" },
      }),
    ).toThrow("Aggregate snapshot request failed");
  });
});
