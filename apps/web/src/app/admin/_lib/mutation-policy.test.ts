import { existsSync } from "node:fs";
import path from "node:path";
import { describe, expect, it, vi } from "vitest";

const moduleFile = path.resolve(process.cwd(), "src/app/admin/_lib/mutation-policy.ts");
const VERIFIED_ACTOR = {
  userId: "22222222-2222-4222-8222-222222222222",
  email: "admin@example.com",
} as const;

describe("admin mutation policy", () => {
  it("accepts only a bounded HTTPS source URL and rejects policy-bypass parameters", async () => {
    expect(existsSync(moduleFile)).toBe(true);
    if (!existsSync(moduleFile)) return;
    const modulePath = "./mutation-policy";
    const { parseAdminMutation } = await import(/* @vite-ignore */ modulePath);

    const valid = new FormData();
    valid.set("sourceUrl", " https://example.com/openings ");
    expect(parseAdminMutation("source.enqueue", valid)).toEqual({
      ok: true,
      command: { action: "source.enqueue", sourceUrl: "https://example.com/openings" },
    });

    const query = new FormData();
    query.set("sourceUrl", "https://example.com/openings?token=must-not-audit");
    expect(parseAdminMutation("source.enqueue", query)).toMatchObject({ ok: false });

    const bypass = new FormData();
    bypass.set("sourceUrl", "https://unknown.invalid/item");
    bypass.set("policyApproved", "true");
    expect(parseAdminMutation("source.enqueue", bypass)).toMatchObject({ ok: false });

    const insecure = new FormData();
    insecure.set("sourceUrl", "http://example.com/item");
    expect(parseAdminMutation("source.enqueue", insecure)).toMatchObject({ ok: false });

    const oversized = new FormData();
    oversized.set("sourceUrl", `https://example.com/${"a".repeat(2048)}`);
    expect(parseAdminMutation("source.enqueue", oversized)).toMatchObject({ ok: false });
  });

  it("accepts only format-specific bounded CSV, JSONL and OpenCLI files", async () => {
    const modulePath = "./mutation-policy";
    const { ADMIN_IMPORT_LIMITS, parseAdminMutation } = await import(/* @vite-ignore */ modulePath);
    const cases = [
      ["import.csv", "observations.CSV", "text/csv", "csv"],
      ["import.jsonl", "observations.ndjson", "application/x-ndjson", "jsonl"],
      ["import.opencli", "opencli-export.json", "application/json", "opencli"],
    ] as const;

    for (const [action, name, type, importKind] of cases) {
      const exact = new FormData();
      exact.set("file", new File([new Uint8Array(ADMIN_IMPORT_LIMITS[importKind])], name, { type }));
      expect(parseAdminMutation(action, exact)).toEqual({
        ok: true,
        command: { action, importKind, byteLength: ADMIN_IMPORT_LIMITS[importKind] },
      });

      const oversized = new FormData();
      oversized.set("file", new File([new Uint8Array(ADMIN_IMPORT_LIMITS[importKind] + 1)], name, { type }));
      expect(parseAdminMutation(action, oversized)).toMatchObject({ ok: false });
    }

    const wrongExtension = new FormData();
    wrongExtension.set("file", new File(["{}"], "opencli-export.txt", { type: "application/json" }));
    expect(parseAdminMutation("import.opencli", wrongExtension)).toMatchObject({ ok: false });

    const profileBypass = new FormData();
    profileBypass.set("file", new File(["{}"], "opencli-export.json", { type: "application/json" }));
    profileBypass.set("browserProfile", "operator-profile");
    expect(parseAdminMutation("import.opencli", profileBypass)).toMatchObject({ ok: false });
  });

  it("parses each explicit control action from only one opaque target id", async () => {
    const modulePath = "./mutation-policy";
    const { parseAdminMutation } = await import(/* @vite-ignore */ modulePath);
    const actions = [
      "job.retry",
      "job.cancel",
      "source.disable",
      "record.exclude",
      "browser.refresh",
      "service.restart",
    ] as const;

    for (const action of actions) {
      const form = new FormData();
      form.set("targetId", "fixture:item-01");
      expect(parseAdminMutation(action, form)).toEqual({
        ok: true,
        command: { action, targetId: "fixture:item-01" },
      });
    }

    const forceRetry = new FormData();
    forceRetry.set("targetId", "job-01");
    forceRetry.set("force", "true");
    expect(parseAdminMutation("job.retry", forceRetry)).toMatchObject({ ok: false });

    const pathTarget = new FormData();
    pathTarget.set("targetId", "../../browser-profile");
    expect(parseAdminMutation("browser.refresh", pathTarget)).toMatchObject({ ok: false });
  });

  it("does not invoke or revalidate when the restricted control RPC is disabled", async () => {
    const modulePath = "./mutation-policy";
    const { executeAdminMutation } = await import(/* @vite-ignore */ modulePath);
    const invoke = vi.fn();
    const revalidate = vi.fn();

    const result = await executeAdminMutation(
      { action: "job.cancel", targetId: "job-01" },
      VERIFIED_ACTOR,
      { enabled: false, invoke, revalidate, invalidatePublicDashboard: vi.fn() },
    );

    expect(result).toEqual({
      status: "unavailable",
      message: "This control is disabled until the restricted, audited admin RPC is configured.",
    });
    expect(invoke).not.toHaveBeenCalled();
    expect(revalidate).not.toHaveBeenCalled();
  });

  it("binds the verified Supabase actor to every audited RPC request", async () => {
    const modulePath = "./mutation-policy";
    const { ADMIN_CONTROL_RPC_NAME, executeAdminMutation } = await import(/* @vite-ignore */ modulePath);
    const invoke = vi.fn().mockResolvedValue({
      data: { ok: true, audit_written: true },
      error: null,
    });
    const revalidate = vi.fn();

    const result = await executeAdminMutation(
      { action: "job.cancel", targetId: "11111111-1111-4111-8111-111111111111" },
      {
        userId: "22222222-2222-4222-8222-222222222222",
        email: "admin@example.com",
      },
      { enabled: true, invoke, revalidate, invalidatePublicDashboard: vi.fn() },
    );

    expect(result.status).toBe("success");
    expect(invoke).toHaveBeenCalledWith(ADMIN_CONTROL_RPC_NAME, {
      p_action: "job.cancel",
      p_actor_id: "22222222-2222-4222-8222-222222222222",
      p_actor_email: "admin@example.com",
      p_source_url: null,
      p_target_id: "11111111-1111-4111-8111-111111111111",
    });
  });

  it("enqueues a source only through an audited RPC that proves policy validation", async () => {
    const modulePath = "./mutation-policy";
    const { ADMIN_CONTROL_RPC_NAME, executeAdminMutation } = await import(/* @vite-ignore */ modulePath);
    const invoke = vi.fn().mockResolvedValue({
      data: { ok: true, audit_written: true, policy_validated: true },
      error: null,
    });
    const revalidate = vi.fn();

    const result = await executeAdminMutation(
      { action: "source.enqueue", sourceUrl: "https://example.com/openings" },
      VERIFIED_ACTOR,
      { enabled: true, invoke, revalidate, invalidatePublicDashboard: vi.fn() },
    );

    expect(invoke).toHaveBeenCalledWith(ADMIN_CONTROL_RPC_NAME, {
      p_action: "source.enqueue",
      p_actor_id: VERIFIED_ACTOR.userId,
      p_actor_email: VERIFIED_ACTOR.email,
      p_source_url: "https://example.com/openings",
      p_target_id: null,
    });
    expect(result).toEqual({ status: "success", message: "The audited control request was accepted." });
    expect(revalidate).toHaveBeenCalledOnce();
    expect(revalidate).toHaveBeenCalledWith("/admin/sources");

    invoke.mockResolvedValueOnce({ data: { ok: true, audit_written: true }, error: null });
    revalidate.mockClear();
    const unproven = await executeAdminMutation(
      { action: "source.enqueue", sourceUrl: "https://example.com/another" },
      VERIFIED_ACTOR,
      { enabled: true, invoke, revalidate, invalidatePublicDashboard: vi.fn() },
    );
    expect(unproven).toEqual({ status: "failed", message: "The control request was not accepted." });
    expect(revalidate).not.toHaveBeenCalled();
  });

  it("executes explicit controls only with audit proof and revalidates the affected route", async () => {
    const modulePath = "./mutation-policy";
    const { ADMIN_CONTROL_RPC_NAME, executeAdminMutation } = await import(/* @vite-ignore */ modulePath);
    const invoke = vi.fn().mockResolvedValue({ data: { ok: true, audit_written: true }, error: null });
    const revalidate = vi.fn();
    const cases = [
      ["job.retry", "/admin/jobs"],
      ["job.cancel", "/admin/jobs"],
      ["source.disable", "/admin/sources"],
      ["record.exclude", "/admin/sources"],
      ["browser.refresh", "/admin/browser"],
      ["service.restart", "/admin/system"],
    ] as const;

    for (const [action, route] of cases) {
      invoke.mockClear();
      revalidate.mockClear();
      const result = await executeAdminMutation(
        { action, targetId: "fixture:item-01" },
        VERIFIED_ACTOR,
        { enabled: true, invoke, revalidate, invalidatePublicDashboard: vi.fn() },
      );
      expect(result).toMatchObject({ status: "success" });
      expect(invoke).toHaveBeenCalledWith(ADMIN_CONTROL_RPC_NAME, {
        p_action: action,
        p_actor_id: VERIFIED_ACTOR.userId,
        p_actor_email: VERIFIED_ACTOR.email,
        p_source_url: null,
        p_target_id: "fixture:item-01",
      });
      expect(revalidate).toHaveBeenCalledWith(route);
    }

    invoke.mockResolvedValueOnce({ data: { ok: true }, error: null });
    revalidate.mockClear();
    const unaudited = await executeAdminMutation(
      { action: "job.retry", targetId: "job-01" },
      VERIFIED_ACTOR,
      { enabled: true, invoke, revalidate, invalidatePublicDashboard: vi.fn() },
    );
    expect(unaudited).toMatchObject({ status: "failed" });
    expect(revalidate).not.toHaveBeenCalled();
  });

  it("invalidates the public dashboard cache after excluding a record", async () => {
    const modulePath = "./mutation-policy";
    const { executeAdminMutation } = await import(/* @vite-ignore */ modulePath);
    const invoke = vi.fn().mockResolvedValue({
      data: { ok: true, audit_written: true },
      error: null,
    });
    const revalidate = vi.fn();
    const invalidatePublicDashboard = vi.fn();

    const result = await executeAdminMutation(
      { action: "record.exclude", targetId: "record-01" },
      VERIFIED_ACTOR,
      { enabled: true, invoke, revalidate, invalidatePublicDashboard },
    );

    expect(result).toMatchObject({ status: "success" });
    expect(revalidate).toHaveBeenCalledWith("/admin/sources");
    expect(invalidatePublicDashboard).toHaveBeenCalledOnce();
  });

  it("converts RPC failures to a fixed public message without leaking internals", async () => {
    const modulePath = "./mutation-policy";
    const { executeAdminMutation } = await import(/* @vite-ignore */ modulePath);
    const invoke = vi.fn().mockRejectedValue(
      new Error("postgres://operator:secret@db.internal service_role=top-secret\n at privateStack"),
    );
    const revalidate = vi.fn();

    const result = await executeAdminMutation(
      { action: "service.restart", targetId: "worker-01" },
      VERIFIED_ACTOR,
      { enabled: true, invoke, revalidate, invalidatePublicDashboard: vi.fn() },
    );

    expect(result).toEqual({ status: "failed", message: "The control request was not accepted." });
    expect(JSON.stringify(result)).not.toMatch(/secret|internal|stack|postgres|service_role/i);
    expect(revalidate).not.toHaveBeenCalled();
  });
});
