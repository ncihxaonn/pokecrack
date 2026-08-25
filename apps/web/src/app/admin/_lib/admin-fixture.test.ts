import { existsSync } from "node:fs";
import path from "node:path";
import { describe, expect, it } from "vitest";

const moduleFile = path.resolve(process.cwd(), "src/app/admin/_lib/admin-fixture.ts");

describe("admin status fixture", () => {
  it("covers required operational status without sensitive fields", async () => {
    expect(existsSync(moduleFile)).toBe(true);
    if (!existsSync(moduleFile)) return;
    const modulePath = "./admin-fixture";
    const { ADMIN_DEMO_FIXTURE } = await import(/* @vite-ignore */ modulePath);

    expect(ADMIN_DEMO_FIXTURE).toMatchObject({
      fixture: true,
      queue: { queued: expect.any(Number), running: expect.any(Number), dead: expect.any(Number) },
      pipeline: {
        accepted: expect.any(Number),
        rejected: expect.any(Number),
        activityOnly: expect.any(Number),
        duplicates: expect.any(Number),
        freshness: expect.any(String),
      },
      ai: {
        inputTokens: expect.any(Number),
        outputTokens: expect.any(Number),
        estimatedCostAud: expect.any(Number),
        budgetAud: expect.any(Number),
        paused: expect.any(Boolean),
      },
      capacity: {
        database: { usedPercent: expect.any(Number), thresholdPercent: expect.any(Number) },
        storage: { usedPercent: expect.any(Number), thresholdPercent: expect.any(Number) },
      },
      backup: { status: expect.any(String), freshness: expect.any(String) },
      aggregation: { status: expect.any(String), freshness: expect.any(String) },
    });
    expect(ADMIN_DEMO_FIXTURE.workers.length).toBeGreaterThan(0);
    expect(ADMIN_DEMO_FIXTURE.browserSessions.length).toBeGreaterThan(0);
    expect(ADMIN_DEMO_FIXTURE.adapters.length).toBeGreaterThan(0);
    expect(ADMIN_DEMO_FIXTURE.label).toMatch(/synthetic fixture/i);

    const serialized = JSON.stringify(ADMIN_DEMO_FIXTURE);
    expect(serialized).not.toMatch(/profile_name|browserProfile|rawPayload|service.role|secret|stack|internal error/i);
  });
});
