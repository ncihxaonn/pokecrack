"use server";

import type { Route } from "next";
import { redirect } from "next/navigation";

import { getEnv } from "@/config/env";
import { evaluateAdminAccess, normalizeAdminEmail, sanitizeAdminReturnPath } from "../_lib/access-policy";
import { createAdminSupabaseClient } from "../_lib/auth";

export interface LoginState {
  readonly status: "idle" | "error" | "sent";
  readonly message: string;
}

export const initialLoginState: LoginState = { status: "idle", message: "" };

export async function loginAction(_previous: LoginState, formData: FormData): Promise<LoginState> {
  const env = getEnv();
  if (!env.supabaseConfigured) return { status: "error", message: "Administrator sign-in is unavailable because Supabase Auth is not configured." };

  const email = normalizeAdminEmail(typeof formData.get("email") === "string" ? String(formData.get("email")) : null);
  if (!email || !env.adminEmails.includes(email)) return { status: "error", message: "Sign-in failed. Use an allowlisted administrator account." };
  const supabase = await createAdminSupabaseClient(env);
  if (!supabase) return { status: "error", message: "Administrator sign-in is unavailable." };

  const method = formData.get("method") === "magic-link" ? "magic-link" : "password";
  if (method === "magic-link") {
    const { error } = await supabase.auth.signInWithOtp({
      email,
      options: { shouldCreateUser: false, emailRedirectTo: `${env.siteUrl}/admin/login` },
    });
    if (error) return { status: "error", message: "Sign-in failed. No account was created." };
    return { status: "sent", message: "If the allowlisted account exists, a sign-in link has been sent." };
  }

  const password = typeof formData.get("password") === "string" ? String(formData.get("password")) : "";
  if (!password) return { status: "error", message: "Enter the administrator password." };
  const { error } = await supabase.auth.signInWithPassword({ email, password });
  if (error) return { status: "error", message: "Sign-in failed. Check the credentials and try again." };

  const { data, error: userError } = await supabase.auth.getUser();
  const decision = userError || !data.user
    ? { kind: "unauthenticated" as const }
    : evaluateAdminAccess(env, {
        id: data.user.id,
        email: data.user.email,
        hasAdminClaim: data.user.app_metadata.pokecrack_admin === true,
      });
  if (decision.kind !== "allowed") {
    await supabase.auth.signOut();
    return { status: "error", message: "Sign-in failed. Use an allowlisted administrator account." };
  }
  redirect(sanitizeAdminReturnPath(formData.get("next")) as Route);
}
