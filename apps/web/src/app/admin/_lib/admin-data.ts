import "server-only";

import { getEnv } from "@/config/env";
import { ADMIN_DASHBOARD_RPC } from "@/data/rpc";
import type { AllowedAdminAccess } from "./access-policy";
import { createAdminControlClient } from "./admin-control-client.server";
import { ADMIN_DEMO_FIXTURE, type AdminStatusData } from "./admin-fixture";
import { liveAdminStatusDataSchema } from "./admin-status-schema";

const ADMIN_UNAVAILABLE_MESSAGE =
  "Admin operational data is unavailable. No demo summary was substituted.";

export type AdminSnapshot =
  | { readonly status: "ready"; readonly synthetic: true; readonly data: AdminStatusData; readonly message: string }
  | { readonly status: "ready"; readonly synthetic: false; readonly data: AdminStatusData; readonly message: string }
  | { readonly status: "unavailable"; readonly synthetic: false; readonly message: string };

function unavailable(): AdminSnapshot {
  return {
    status: "unavailable",
    synthetic: false,
    message: ADMIN_UNAVAILABLE_MESSAGE,
  };
}

export async function getAdminSnapshot(access: AllowedAdminAccess): Promise<AdminSnapshot> {
  if (!access.userId.trim() || !access.email.trim()) return unavailable();
  const env = getEnv();
  if (env.dataMode === "demo") {
    return { status: "ready", synthetic: true, data: ADMIN_DEMO_FIXTURE, message: "Synthetic demo admin summary shown after real Supabase authentication. No operational mutation endpoint is connected." };
  }

  const controlClient = createAdminControlClient({
    supabaseUrl: env.supabaseUrl,
    serviceRoleKey: process.env.SUPABASE_SERVICE_ROLE_KEY,
  });
  if (!controlClient) return unavailable();

  try {
    const { data, error } = await controlClient.rpc(ADMIN_DASHBOARD_RPC);
    if (error) return unavailable();
    const parsed = liveAdminStatusDataSchema.safeParse(data);
    if (!parsed.success) return unavailable();
    return {
      status: "ready",
      synthetic: false,
      data: parsed.data,
      message: "Live operational snapshot loaded from the restricted admin RPC.",
    };
  } catch {
    return unavailable();
  }
}
