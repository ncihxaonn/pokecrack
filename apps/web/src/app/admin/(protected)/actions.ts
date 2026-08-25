"use server";

import { revalidatePath, updateTag } from "next/cache";
import { redirect } from "next/navigation";

import { getEnv } from "@/config/env";
import { createAdminControlClient } from "../_lib/admin-control-client.server";
import { createAdminSupabaseClient, requireAdmin } from "../_lib/auth";
import {
  executeAdminMutation,
  parseAdminMutation,
  type AdminActionName,
} from "../_lib/mutation-policy";

function restrictedControlEnabled(): boolean {
  const env = getEnv();
  return env.dataMode === "live" && process.env.ADMIN_CONTROL_RPC_ENABLED === "true";
}

async function dispatchAdminAction(action: AdminActionName, formData: FormData): Promise<void> {
  const access = await requireAdmin();
  const parsed = parseAdminMutation(action, formData);
  if (!parsed.ok) return;

  const env = getEnv();
  const controlClient = createAdminControlClient({
    supabaseUrl: env.supabaseUrl,
    serviceRoleKey: process.env.SUPABASE_SERVICE_ROLE_KEY,
  });
  await executeAdminMutation(
    parsed.command,
    { userId: access.userId, email: access.email },
    {
      enabled: restrictedControlEnabled() && controlClient !== null,
      invoke: async (rpcName, parameters) => {
        if (!controlClient) return { data: null, error: { code: "UNAVAILABLE" } };
        return controlClient.rpc(rpcName, parameters);
      },
      revalidate: revalidatePath,
      invalidatePublicDashboard: () => updateTag("public-dashboard"),
    },
  );
}

export async function enqueueSourceAction(formData: FormData): Promise<void> {
  await dispatchAdminAction("source.enqueue", formData);
}

export async function importCsvAction(formData: FormData): Promise<void> {
  await dispatchAdminAction("import.csv", formData);
}

export async function importJsonlAction(formData: FormData): Promise<void> {
  await dispatchAdminAction("import.jsonl", formData);
}

export async function importOpenCliAction(formData: FormData): Promise<void> {
  await dispatchAdminAction("import.opencli", formData);
}

export async function retryJobAction(formData: FormData): Promise<void> {
  await dispatchAdminAction("job.retry", formData);
}

export async function cancelJobAction(formData: FormData): Promise<void> {
  await dispatchAdminAction("job.cancel", formData);
}

export async function disableSourceAction(formData: FormData): Promise<void> {
  await dispatchAdminAction("source.disable", formData);
}

export async function excludeRecordAction(formData: FormData): Promise<void> {
  await dispatchAdminAction("record.exclude", formData);
}

export async function refreshBrowserAction(formData: FormData): Promise<void> {
  await dispatchAdminAction("browser.refresh", formData);
}

export async function restartServiceAction(formData: FormData): Promise<void> {
  await dispatchAdminAction("service.restart", formData);
}

export async function signOutAction(): Promise<void> {
  const supabase = await createAdminSupabaseClient();
  if (supabase) await supabase.auth.signOut();
  redirect("/admin/login");
}
