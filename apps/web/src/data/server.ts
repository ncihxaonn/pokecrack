import { createClient } from "@supabase/supabase-js";

import { getEnv, type AppEnv } from "@/config/env";
import { mergePublicStudyCoverage } from "./coverage";
import { resolveDashboardData } from "./resolver";
import {
  PUBLIC_DASHBOARD_RPC,
  PUBLIC_SOCIAL_DISCOVERY_RPC,
  PUBLIC_STUDY_COVERAGE_RPC,
  unwrapRpcSnapshot,
} from "./rpc";
import { mergePublicSocialDiscovery } from "./social-discovery";

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
    const [snapshotResult, coverageResult, socialResult] = await Promise.allSettled([
      supabase.rpc(PUBLIC_DASHBOARD_RPC),
      supabase.rpc(PUBLIC_STUDY_COVERAGE_RPC),
      supabase.rpc(PUBLIC_SOCIAL_DISCOVERY_RPC),
    ]);
    if (snapshotResult.status === "rejected") throw snapshotResult.reason;
    const snapshot = unwrapRpcSnapshot(snapshotResult.value);
    const withCoverage =
      coverageResult.status === "fulfilled" && coverageResult.value.error === null
        ? mergePublicStudyCoverage(snapshot, coverageResult.value.data)
        : snapshot;
    return socialResult.status === "fulfilled" && socialResult.value.error === null
      ? mergePublicSocialDiscovery(withCoverage, socialResult.value.data)
      : withCoverage;
  });
}
