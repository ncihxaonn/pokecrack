import { afterEach, beforeEach, describe, expect, it, vi } from "vitest";

const mocks = vi.hoisted(() => ({
  createAdminControlClient: vi.fn(),
  getEnv: vi.fn(),
  rpc: vi.fn(),
}));

vi.mock("server-only", () => ({}));
vi.mock("@/config/env", () => ({ getEnv: mocks.getEnv }));
vi.mock("./admin-control-client.server", () => ({
  createAdminControlClient: mocks.createAdminControlClient,
}));

import type { AllowedAdminAccess } from "./access-policy";
import { ADMIN_DASHBOARD_RPC } from "@/data/rpc";
import { getAdminSnapshot } from "./admin-data";
import { ADMIN_DEMO_FIXTURE, type AdminStatusData } from "./admin-fixture";

const access: AllowedAdminAccess = {
  kind: "allowed",
  via: "supabase",
  email: "admin@example.com",
  userId: "11111111-1111-4111-8111-111111111111",
};

const liveEnv = {
  dataMode: "live",
  supabaseUrl: "https://project.supabase.co",
};

function livePayload(): AdminStatusData {
  return {
    ...ADMIN_DEMO_FIXTURE,
    fixture: false,
    label: "Live restricted operational snapshot",
    ai: {
      ...ADMIN_DEMO_FIXTURE.ai,
      budgetAud: null,
      paused: false,
    },
  };
}

function expectUnavailable(result: Awaited<ReturnType<typeof getAdminSnapshot>>) {
  expect(result).toEqual({
    status: "unavailable",
    synthetic: false,
    message: "Admin operational data is unavailable. No demo summary was substituted.",
  });
  expect(result).not.toHaveProperty("data");
}

describe("admin snapshot data boundary", () => {
  beforeEach(() => {
    vi.clearAllMocks();
    vi.stubEnv("SUPABASE_SERVICE_ROLE_KEY", ["unit", "test", "role"].join("-"));
    mocks.getEnv.mockReturnValue(liveEnv);
    mocks.createAdminControlClient.mockImplementation(({ supabaseUrl, serviceRoleKey }) =>
      supabaseUrl && serviceRoleKey?.trim() ? { rpc: mocks.rpc } : null,
    );
  });

  afterEach(() => {
    vi.unstubAllEnvs();
  });

  it("returns the synthetic fixture in demo mode without creating a service-role client", async () => {
    mocks.getEnv.mockReturnValue({ dataMode: "demo" });

    const result = await getAdminSnapshot(access);

    expect(result).toMatchObject({ status: "ready", synthetic: true });
    expect(result.status === "ready" && result.data).toBe(ADMIN_DEMO_FIXTURE);
    expect(mocks.createAdminControlClient).not.toHaveBeenCalled();
    expect(mocks.rpc).not.toHaveBeenCalled();
  });

  it("loads and validates a live restricted RPC snapshot after admin authorization", async () => {
    const payload = livePayload();
    mocks.rpc.mockResolvedValue({ data: payload, error: null });

    const result = await getAdminSnapshot(access);

    expect(mocks.createAdminControlClient).toHaveBeenCalledWith({
      supabaseUrl: liveEnv.supabaseUrl,
      serviceRoleKey: process.env.SUPABASE_SERVICE_ROLE_KEY,
    });
    expect(mocks.rpc).toHaveBeenCalledWith(ADMIN_DASHBOARD_RPC);
    expect(result).toMatchObject({
      status: "ready",
      synthetic: false,
      data: { fixture: false, ai: { budgetAud: null, paused: false } },
    });
  });

  it("fails closed when either live service-role configuration value is missing", async () => {
    vi.stubEnv("SUPABASE_SERVICE_ROLE_KEY", "");
    expectUnavailable(await getAdminSnapshot(access));
    expect(mocks.rpc).not.toHaveBeenCalled();

    vi.stubEnv("SUPABASE_SERVICE_ROLE_KEY", ["unit", "test", "role"].join("-"));
    mocks.getEnv.mockReturnValue({ dataMode: "live", supabaseUrl: undefined });
    expectUnavailable(await getAdminSnapshot(access));
    expect(mocks.rpc).not.toHaveBeenCalled();
  });

  it("fails closed on an RPC error or thrown transport failure without leaking details", async () => {
    mocks.rpc.mockResolvedValueOnce({
      data: null,
      error: { message: "private database detail", code: "XX999" },
    });
    const rpcError = await getAdminSnapshot(access);
    expectUnavailable(rpcError);
    expect(JSON.stringify(rpcError)).not.toMatch(/private database detail|XX999/);

    mocks.rpc.mockRejectedValueOnce(new Error("private transport detail"));
    const thrownError = await getAdminSnapshot(access);
    expectUnavailable(thrownError);
    expect(JSON.stringify(thrownError)).not.toMatch(/private transport detail/);
  });

  it("rejects malformed, non-live, and non-strict RPC payloads", async () => {
    for (const payload of [
      { fixture: false },
      { ...livePayload(), fixture: true },
      { ...livePayload(), unexpectedPrivateField: "must not pass" },
    ]) {
      mocks.rpc.mockResolvedValueOnce({ data: payload, error: null });
      expectUnavailable(await getAdminSnapshot(access));
    }
  });

  it("rejects payloads beyond array, string, or numeric bounds", async () => {
    const worker = livePayload().workers[0]!;
    const oversizedPayloads = [
      {
        ...livePayload(),
        workers: Array.from({ length: 51 }, (_, index) => ({
          ...worker,
          id: `worker-${index}`,
        })),
      },
      { ...livePayload(), label: "x".repeat(201) },
      {
        ...livePayload(),
        queue: { ...livePayload().queue, queued: Number.MAX_SAFE_INTEGER + 1 },
      },
    ];

    for (const payload of oversizedPayloads) {
      mocks.rpc.mockResolvedValueOnce({ data: payload, error: null });
      expectUnavailable(await getAdminSnapshot(access));
    }
  });

  it("matches PostgreSQL Unicode and numeric bounds without rejecting legal telemetry", async () => {
    const payload = livePayload();
    const source = payload.sources[0]!;
    mocks.rpc.mockResolvedValueOnce({
      data: {
        ...payload,
        sources: [{ ...source, label: "😀".repeat(160) }],
        queue: { ...payload.queue, queued: 10_000_001 },
        ai: {
          ...payload.ai,
          requests: 10_000_001,
          inputTokens: 1_000_000_000_001,
          outputTokens: 1_000_000_000_001,
          estimatedCostAud: 1_000_000.01,
        },
      },
      error: null,
    });
    expect((await getAdminSnapshot(access)).status).toBe("ready");

    mocks.rpc.mockResolvedValueOnce({
      data: { ...payload, sources: [{ ...source, label: "\u00a0" }] },
      error: null,
    });
    expect((await getAdminSnapshot(access)).status).toBe("ready");

    mocks.rpc.mockResolvedValueOnce({
      data: { ...payload, sources: [{ ...source, label: "😀".repeat(161) }] },
      error: null,
    });
    expectUnavailable(await getAdminSnapshot(access));
  });
});
