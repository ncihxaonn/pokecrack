import type { AppEnv, DataMode } from "@/config/env";
import { DEMO_PUBLIC_DATA } from "./demo";
import { publicDashboardDataSchema } from "./schema";
import type { PublicDashboardData } from "./types";

export type DataUnavailableCode =
  | "supabase-unconfigured"
  | "upstream-unavailable"
  | "invalid-payload";

export type DashboardResult =
  | {
      readonly status: "ready";
      readonly mode: DataMode;
      readonly synthetic: boolean;
      readonly data: PublicDashboardData;
    }
  | {
      readonly status: "unavailable";
      readonly mode: "live";
      readonly code: DataUnavailableCode;
      readonly message: string;
    };

export type LiveDashboardLoader = () => Promise<unknown>;

const LIVE_UNAVAILABLE_MESSAGE =
  "Live aggregate data is currently unavailable. Demo fixtures were not substituted.";

function unavailable(code: DataUnavailableCode): DashboardResult {
  return {
    status: "unavailable",
    mode: "live",
    code,
    message: LIVE_UNAVAILABLE_MESSAGE,
  };
}

export async function resolveDashboardData(
  env: AppEnv,
  loadLive: LiveDashboardLoader,
): Promise<DashboardResult> {
  if (env.dataMode === "demo") {
    return {
      status: "ready",
      mode: "demo",
      synthetic: true,
      data: DEMO_PUBLIC_DATA,
    };
  }

  if (!env.supabaseConfigured) return unavailable("supabase-unconfigured");

  let payload: unknown;
  try {
    payload = await loadLive();
  } catch {
    return unavailable("upstream-unavailable");
  }

  const parsed = publicDashboardDataSchema.safeParse(payload);
  if (!parsed.success || parsed.data.mode !== "live") {
    return unavailable("invalid-payload");
  }

  return {
    status: "ready",
    mode: "live",
    synthetic: false,
    data: parsed.data,
  };
}
