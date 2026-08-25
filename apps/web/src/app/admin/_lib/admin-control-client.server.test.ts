import { describe, expect, it, vi } from "vitest";

vi.mock("server-only", () => ({}));

import { createAdminControlClient } from "./admin-control-client.server";

describe("admin control service client", () => {
  it("fails closed unless a server-only service role key is configured", () => {
    const factory = vi.fn();

    expect(createAdminControlClient({
      supabaseUrl: "https://project.supabase.co",
      serviceRoleKey: undefined,
      factory,
    })).toBeNull();
    expect(factory).not.toHaveBeenCalled();
  });

  it("creates a non-persistent server client with the service role key", () => {
    const sentinel = { rpc: vi.fn() };
    const factory = vi.fn(() => sentinel);

    const result = createAdminControlClient({
      supabaseUrl: "https://project.supabase.co",
      serviceRoleKey: "fixture-service-role-key",
      factory,
    });

    expect(result).toBe(sentinel);
    expect(factory).toHaveBeenCalledWith(
      "https://project.supabase.co",
      "fixture-service-role-key",
      {
        auth: {
          autoRefreshToken: false,
          detectSessionInUrl: false,
          persistSession: false,
        },
      },
    );
  });
});
