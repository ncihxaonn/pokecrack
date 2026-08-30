import { createClient } from "@supabase/supabase-js";

import { getEnv, type AppEnv } from "@/config/env";
import { mergePublicStudyCoverage } from "./coverage";
import { resolveDashboardData } from "./resolver";
import {
  PUBLIC_DASHBOARD_RPC,
  PUBLIC_STUDY_COVERAGE_RPC,
  unwrapRpcSnapshot,
} from "./rpc";

export function createPublicSupabaseClient(env: AppEnv = getEnv()) {
  if (!env.supabaseUrl || !env.supabasePublishableKey) return null;
  return createClient(env.supabaseUrl, env.supabasePublishableKey, {
    auth: {
      autoRefreshToken: false,
      detectSessionInUrl: false,
      persistSession: false,
    },
  });
}

export async function getDashboardData() {
  const env = getEnv();
  return resolveDashboardData(env, async () => {
    const supabase = createPublicSupabaseClient(env);
    if (!supabase) throw new Error("Supabase is not configured");
    const [snapshotResult, coverageResult] = await Promise.allSettled([
      supabase.rpc(PUBLIC_DASHBOARD_RPC),
      supabase.rpc(PUBLIC_STUDY_COVERAGE_RPC),
    ]);
    if (snapshotResult.status === "rejected") throw snapshotResult.reason;
    const snapshot = unwrapRpcSnapshot(snapshotResult.value);
    if (
      coverageResult.status === "rejected" ||
      coverageResult.value.error !== null
    ) return snapshot;
    return mergePublicStudyCoverage(snapshot, coverageResult.value.data);
  });
}
