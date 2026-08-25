import "server-only";

import { createClient, type SupabaseClient } from "@supabase/supabase-js";

const CLIENT_OPTIONS = {
  auth: {
    autoRefreshToken: false,
    detectSessionInUrl: false,
    persistSession: false,
  },
} as const;

type AdminClientFactory<TClient> = (
  url: string,
  key: string,
  options: typeof CLIENT_OPTIONS,
) => TClient;

export interface AdminControlClientOptions<TClient> {
  readonly supabaseUrl?: string;
  readonly serviceRoleKey?: string;
  readonly factory?: AdminClientFactory<TClient>;
}

export function createAdminControlClient<TClient = SupabaseClient>({
  supabaseUrl,
  serviceRoleKey,
  factory = createClient as AdminClientFactory<TClient>,
}: AdminControlClientOptions<TClient>): TClient | null {
  if (!supabaseUrl || !serviceRoleKey?.trim()) return null;
  return factory(supabaseUrl, serviceRoleKey, CLIENT_OPTIONS);
}
