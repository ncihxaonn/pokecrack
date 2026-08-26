import { beforeEach, describe, expect, it, vi } from "vitest";

import { parseEnv } from "@/config/env";

const mocks = vi.hoisted(() => ({
  createAdminSupabaseClient: vi.fn(),
  evaluateAdminAccess: vi.fn(),
  getEnv: vi.fn(),
  redirect: vi.fn(),
}));

vi.mock("next/navigation", () => ({ redirect: mocks.redirect }));
vi.mock("@/config/env", async (importOriginal) => ({
  ...await importOriginal<typeof import("@/config/env")>(),
  getEnv: mocks.getEnv,
}));
vi.mock("../_lib/auth", () => ({
  createAdminSupabaseClient: mocks.createAdminSupabaseClient,
}));
vi.mock("../_lib/access-policy", async (importOriginal) => ({
  ...await importOriginal<typeof import("../_lib/access-policy")>(),
  evaluateAdminAccess: mocks.evaluateAdminAccess,
}));

import { initialLoginState, loginAction } from "./actions";

describe("admin password login", () => {
  beforeEach(() => {
    vi.clearAllMocks();
  });

  it("authorizes the complete verified Supabase identity before redirecting", async () => {
    const env = parseEnv({
      DATA_MODE: "live",
      NEXT_PUBLIC_SUPABASE_URL: "https://project.supabase.co",
      NEXT_PUBLIC_SUPABASE_PUBLISHABLE_KEY: "public-key",
      ADMIN_EMAILS: "admin@example.com",
    });
    const user = {
      id: "11111111-1111-4111-8111-111111111111",
      email: "admin@example.com",
      app_metadata: { pokecrack_admin: true, provider: "email" },
    };
    const signInWithPassword = vi.fn().mockResolvedValue({ error: null });
    const getUser = vi.fn().mockResolvedValue({ data: { user }, error: null });
    const signOut = vi.fn();
    mocks.getEnv.mockReturnValue(env);
    mocks.createAdminSupabaseClient.mockResolvedValue({
      auth: { signInWithPassword, getUser, signOut },
    });
    mocks.evaluateAdminAccess.mockReturnValue({
      kind: "allowed",
      via: "supabase",
      email: user.email,
      userId: user.id,
    });
    mocks.redirect.mockImplementation(() => {
      throw new Error("NEXT_REDIRECT");
    });

    const submittedPassword = ["unit", "test", "input"].join("-");
    const formData = new FormData();
    formData.set("email", user.email);
    formData.set("password", submittedPassword);
    formData.set("method", "password");
    formData.set("next", "/admin/jobs");

    await expect(loginAction(initialLoginState, formData)).rejects.toThrow("NEXT_REDIRECT");

    expect(signInWithPassword).toHaveBeenCalledWith({
      email: user.email,
      password: submittedPassword,
    });
    expect(getUser).toHaveBeenCalledOnce();
    expect(mocks.evaluateAdminAccess).toHaveBeenCalledWith(env, {
      id: user.id,
      email: user.email,
      hasAdminClaim: true,
    });
    expect(signOut).not.toHaveBeenCalled();
    expect(mocks.redirect).toHaveBeenCalledWith("/admin/jobs");
  });
});
