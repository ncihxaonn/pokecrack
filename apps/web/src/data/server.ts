import { createClient } from "@supabase/supabase-js";

import { getEnv, type AppEnv } from "@/config/env";
import { resolveDashboardData } from "./resolver";
import { PUBLIC_DASHBOARD_RPC, unwrapRpcSnapshot } from "./rpc";

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
    const response = await supabase.rpc(PUBLIC_DASHBOARD_RPC);
    return unwrapRpcSnapshot(response);
  });
}
