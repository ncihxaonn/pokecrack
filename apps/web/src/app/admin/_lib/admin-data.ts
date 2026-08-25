import "server-only";

import { getEnv } from "@/config/env";
import { DEMO_ADMIN_DATA } from "@/data/demo";
import type { AdminDashboardData } from "@/data/types";
import type { AllowedAdminAccess } from "./access-policy";

export type AdminSnapshot =
  | { readonly status: "ready"; readonly synthetic: true; readonly data: AdminDashboardData; readonly message: string }
  | { readonly status: "unavailable"; readonly synthetic: false; readonly message: string };

export async function getAdminSnapshot(access: AllowedAdminAccess): Promise<AdminSnapshot> {
  void access;
  const env = getEnv();
  if (env.dataMode === "demo") {
    return { status: "ready", synthetic: true, data: DEMO_ADMIN_DATA, message: "Synthetic demo admin summary shown after real Supabase authentication. No operational mutation endpoint is connected." };
  }
  return { status: "unavailable", synthetic: false, message: "Admin operational data is unavailable in this web process. No demo summary was substituted." };
}
