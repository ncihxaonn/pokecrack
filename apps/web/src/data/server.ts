import { createClient } from "@supabase/supabase-js";

import { getEnv, type AppEnv } from "@/config/env";
import {
  mergePublicStudyCoverage,
  publicStudyCoverageSchema,
} from "./coverage";
import { resolveDashboardData } from "./resolver";
import {
  PUBLIC_DASHBOARD_RPC,
  PUBLIC_SOCIAL_DISCOVERY_FALLBACK_RPC,
  PUBLIC_SOCIAL_DISCOVERY_RPC,
  PUBLIC_STUDY_COVERAGE_FALLBACK_RPC,
  PUBLIC_STUDY_COVERAGE_LEGACY_RPC,
  PUBLIC_STUDY_COVERAGE_OLDEST_RPC,
  PUBLIC_STUDY_COVERAGE_RPC,
  unwrapRpcSnapshot,
} from "./rpc";
import {
  mergePublicSocialDiscovery,
  publicSocialDiscoveryV4Schema,
} from "./social-discovery";

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

async function mergeSocialProvenance(
  supabase: NonNullable<ReturnType<typeof createPublicSupabaseClient>>,
  snapshot: unknown,
) {
  try {
    const fallbackResult = await supabase.rpc(PUBLIC_SOCIAL_DISCOVERY_FALLBACK_RPC);
    return fallbackResult.error === null
      ? mergePublicSocialDiscovery(snapshot, fallbackResult.data)
      : snapshot;
  } catch {
    return snapshot;
  }
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
    const coveragePayload =
      coverageResult.status === "fulfilled" &&
        coverageResult.value.error === null &&
        (coverageResult.value.data === null ||
          publicStudyCoverageSchema.safeParse(coverageResult.value.data).success)
        ? coverageResult.value.data
        : await (async () => {
            for (const rpc of [PUBLIC_STUDY_COVERAGE_FALLBACK_RPC,
              PUBLIC_STUDY_COVERAGE_LEGACY_RPC, PUBLIC_STUDY_COVERAGE_OLDEST_RPC]) {
              try {
                const fallback = await supabase.rpc(rpc);
                if (fallback.error === null && (fallback.data === null ||
                  publicStudyCoverageSchema.safeParse(fallback.data).success)) return fallback.data;
              } catch {
                // A partially rolled-out database must retain older coverage.
              }
            }
            return null;
          })();
    const withCoverage =
      coveragePayload === null ? snapshot : mergePublicStudyCoverage(snapshot, coveragePayload);
    if (socialResult.status === "fulfilled" && socialResult.value.error === null) {
      const withPulse = mergePublicSocialDiscovery(withCoverage, socialResult.value.data);
      if (publicSocialDiscoveryV4Schema.safeParse(socialResult.value.data).success) {
        return mergeSocialProvenance(supabase, withPulse);
      }
      return withPulse;
    }

    return mergeSocialProvenance(supabase, withCoverage);
  });
}
