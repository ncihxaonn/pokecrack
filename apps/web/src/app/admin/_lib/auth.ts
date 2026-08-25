import "server-only";

import { createServerClient } from "@supabase/ssr";
import { cookies } from "next/headers";
import { redirect } from "next/navigation";
import { cache } from "react";

import { getEnv, type AppEnv } from "@/config/env";
import { enforceAdminAccess, evaluateAdminAccess, type AdminAccessDecision, type AllowedAdminAccess } from "./access-policy";

export async function createAdminSupabaseClient(env: AppEnv = getEnv()) {
  if (!env.supabaseUrl || !env.supabasePublishableKey) return null;
  const cookieStore = await cookies();
  return createServerClient(env.supabaseUrl, env.supabasePublishableKey, {
    cookies: {
      getAll: () => cookieStore.getAll(),
      setAll(cookiesToSet) {
        try {
          for (const { name, value, options } of cookiesToSet) cookieStore.set(name, value, options);
        } catch {
          // The proxy refreshes cookies before Server Components render.
        }
      },
    },
  });
}

export const readAdminAccess = cache(async (): Promise<AdminAccessDecision> => {
  const env = getEnv();
  if (!env.supabaseConfigured) return { kind: "unauthenticated" };

  const supabase = await createAdminSupabaseClient(env);
  if (!supabase) return { kind: "unauthenticated" };
  const { data, error } = await supabase.auth.getUser();
  if (error || !data.user) return { kind: "unauthenticated" };
  return evaluateAdminAccess(env, {
    id: data.user.id,
    email: data.user.email,
    hasAdminClaim: data.user.app_metadata.pokecrack_admin === true,
  });
});

export const requireAdmin = cache(async (): Promise<AllowedAdminAccess> => {
  const decision = await readAdminAccess();
  if (decision.kind === "unauthenticated") redirect("/admin/login");
  return enforceAdminAccess(decision);
});
