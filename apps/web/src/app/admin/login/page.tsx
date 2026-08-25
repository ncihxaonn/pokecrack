import React from "react";
import type { Metadata, Route } from "next";
import { redirect } from "next/navigation";

import { BRAND } from "@/config/brand";
import { getEnv } from "@/config/env";
import { createPageMetadata } from "../../_lib/metadata";
import { sanitizeAdminReturnPath } from "../_lib/access-policy";
import { createAdminSupabaseClient, readAdminAccess } from "../_lib/auth";
import { LoginForm } from "./login-form";

export const dynamic = "force-dynamic";
export const metadata: Metadata = createPageMetadata("Admin sign in", "Restricted administrator authentication.", "/admin/login", { index: false });

type SearchParams = Promise<{ next?: string | string[]; code?: string | string[] }>;

export default async function AdminLoginPage({ searchParams }: { searchParams: SearchParams }) {
  const query = await searchParams;
  const code = Array.isArray(query.code) ? query.code[0] : query.code;
  if (code && code.length <= 2048) {
    const env = getEnv();
    const supabase = await createAdminSupabaseClient(env);
    if (supabase) await supabase.auth.exchangeCodeForSession(code);
  }
  const access = await readAdminAccess();
  if (access.kind === "allowed") redirect(sanitizeAdminReturnPath(query.next) as Route);

  return <div className="page-shell login-page"><section className="login-card"><span className="eyebrow">{BRAND.shortName} / restricted</span><h1>Administrator sign in</h1><p>Use an allowlisted Supabase account. Authentication and the server guard both fail closed.</p>{access.kind === "forbidden" ? <p className="form-message form-message--error" role="alert">The current authenticated account is not allowlisted.</p> : null}<LoginForm nextPath={sanitizeAdminReturnPath(query.next)} /></section><aside className="login-aside"><code>ACCESS_POLICY</code><ul><li>Public signup is disabled.</li><li>Email matching is normalized and allowlist-only.</li><li>Service credentials never enter the browser bundle.</li><li>Every admin request is session-verified server-side.</li></ul></aside></div>;
}
