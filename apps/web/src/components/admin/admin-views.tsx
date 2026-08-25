import React, { type ReactNode } from "react";
import Link from "next/link";

import { BRAND } from "@/config/brand";
import type { AdminDashboardData } from "@/data/types";
import { formatCompactNumber, formatDate, formatDateTime } from "@/lib/format";
import { Panel, TableFrame } from "@/components/ui/dashboard-ui";

const adminNavigation = [
  { href: "/admin", label: "Overview" },
  { href: "/admin/sources", label: "Sources" },
  { href: "/admin/jobs", label: "Jobs" },
  { href: "/admin/browser", label: "Browser" },
  { href: "/admin/ai-usage", label: "AI usage" },
  { href: "/admin/system", label: "System" },
] as const;

export function AdminShell({ email, via, children }: { email: string; via: "supabase"; children: ReactNode }) {
  return (
    <div className="admin-shell">
      <aside className="admin-sidebar">
        <div><span className="eyebrow">Control plane</span><strong>{BRAND.shortName} / ADMIN</strong><small>{email}</small><span className={`admin-session admin-session--${via}`}>Verified Supabase user</span></div>
        <nav aria-label="Admin navigation"><ul>{adminNavigation.map((item) => <li key={item.href}><Link href={item.href}>{item.label}</Link></li>)}</ul></nav>
        <p>Operational summaries are read-only unless a policy-validating, audited server endpoint is explicitly connected.</p>
      </aside>
      <div className="admin-content">{children}</div>
    </div>
  );
}

export function AdminHeading({ title, description }: { title: string; description: string }) {
  return <header className="admin-heading"><span className="eyebrow">Restricted · noindex</span><h1>{title}</h1><p>{description}</p></header>;
}

export function AdminModeNotice({ message, synthetic }: { message: string; synthetic: boolean }) {
  return <aside className={`admin-mode ${synthetic ? "admin-mode--demo" : "admin-mode--unavailable"}`} role="status"><strong>{synthetic ? "SYNTHETIC / READ ONLY" : "UNAVAILABLE / FAIL CLOSED"}</strong><p>{message}</p></aside>;
}

export function DisabledMutation({ label, reason }: { label: string; reason: string }) {
  return <div className="disabled-action"><button className="button button--secondary" type="button" disabled>{label}</button><small>{reason}</small></div>;
}

function EmptyAdmin({ message }: { message: string }) {
  return <Panel><p className="empty-cell">{message}</p></Panel>;
}

export function AdminOverview({ snapshot }: { snapshot: { status: "ready"; data: AdminDashboardData } | { status: "unavailable" } }) {
  if (snapshot.status === "unavailable") return <EmptyAdmin message="No operational counts are available." />;
  const attention = snapshot.data.system.filter((item) => item.status !== "ok").length;
  return <div className="admin-kpis"><Panel><span>Jobs</span><strong>{snapshot.data.jobs.length}</strong><small>{snapshot.data.jobs.filter((job) => job.status === "failed").length} failed</small></Panel><Panel><span>Browser profiles</span><strong>{snapshot.data.browserSessions.length}</strong><small>{snapshot.data.browserSessions.filter((item) => item.status === "ready").length} ready</small></Panel><Panel><span>AI ledger rows</span><strong>{snapshot.data.aiUsage.length}</strong><small>synthetic budget summary</small></Panel><Panel><span>System attention</span><strong>{attention}</strong><small>warning or error</small></Panel></div>;
}

export function AdminSourcesView({ available }: { available: boolean }) {
  return <><div className="admin-grid"><Panel><h2>Source policy registry</h2><p>The deployment-managed allowlist is not mutable from this route. Unknown domains and routes remain disabled.</p><DisabledMutation label="Add source" reason="Disabled: requires source-policy validation and an append-only audit write." /></Panel><Panel><h2>Required enablement record</h2><ul className="admin-checklist"><li>Exact domain and enabled route</li><li>Terms, robots and authentication basis</li><li>Rate, concurrency, page and retention bounds</li><li>Statistics-eligibility default and kill switch</li><li>Named owner, review date and adapter fixture</li></ul></Panel></div>{!available ? <EmptyAdmin message="Live source-policy status is unavailable; no synthetic registry was substituted." /> : <Panel><p>Demo mode exposes no editable policy records. Configuration remains deployment-managed.</p></Panel>}</>;
}

export function AdminJobsView({ data }: { data: AdminDashboardData | null }) {
  if (!data) return <EmptyAdmin message="Job status is unavailable." />;
  return <Panel><TableFrame label="Admin jobs"><table><thead><tr><th>Job</th><th>Status</th><th>Last run</th><th>Next run</th><th>Records</th><th>Action</th></tr></thead><tbody>{data.jobs.length === 0 ? <tr><td colSpan={6} className="empty-cell">No jobs are available.</td></tr> : data.jobs.map((job) => <tr key={job.id}><td><strong>{job.name}</strong><small><code>{job.id}</code></small></td><td>{job.status}</td><td>{formatDateTime(job.lastRunAt)}</td><td>{formatDateTime(job.nextRunAt)}</td><td>{formatCompactNumber(job.records)}</td><td><button type="button" disabled>Run disabled</button></td></tr>)}</tbody></table></TableFrame><p className="admin-footnote">Job mutations are disabled because this web shell has no policy-validating, audited queue endpoint.</p></Panel>;
}

export function AdminBrowserView({ data }: { data: AdminDashboardData | null }) {
  if (!data) return <EmptyAdmin message="Browser-session status is unavailable." />;
  return <div className="admin-grid">{data.browserSessions.length === 0 ? <EmptyAdmin message="No browser-session summaries are available." /> : data.browserSessions.map((session) => <Panel key={session.id}><span className={`status-dot status-dot--${session.status === "ready" ? "operational" : "warning"}`} /><h2>{session.source}</h2><dl className="definition-list"><div><dt>Status</dt><dd>{session.status}</dd></div><div><dt>Profile</dt><dd><code>{session.profile}</code></dd></div><div><dt>Last verified</dt><dd>{formatDateTime(session.lastVerifiedAt)}</dd></div></dl><DisabledMutation label="Open session" reason="Disabled: operator action belongs on the loopback-only VPS console." /></Panel>)}</div>;
}

export function AdminAiUsageView({ data }: { data: AdminDashboardData | null }) {
  if (!data) return <EmptyAdmin message="AI usage ledger is unavailable." />;
  return <Panel><TableFrame label="AI usage ledger"><table><thead><tr><th>Day</th><th>Stage</th><th>Requests</th><th>Input tokens</th><th>Output tokens</th><th>Estimated AUD</th></tr></thead><tbody>{data.aiUsage.length === 0 ? <tr><td colSpan={6} className="empty-cell">No AI usage rows are available.</td></tr> : data.aiUsage.map((row) => <tr key={`${row.day}-${row.stage}`}><td>{formatDate(row.day)}</td><td>{row.stage}</td><td>{formatCompactNumber(row.requests)}</td><td>{formatCompactNumber(row.inputTokens)}</td><td>{formatCompactNumber(row.outputTokens)}</td><td>${row.estimatedAud.toFixed(2)}</td></tr>)}</tbody></table></TableFrame><p className="admin-footnote">Displayed costs are snapshot estimates, not provider billing telemetry.</p></Panel>;
}

export function AdminSystemView({ data }: { data: AdminDashboardData | null }) {
  if (!data) return <EmptyAdmin message="System summary is unavailable." />;
  return <div className="admin-grid">{data.system.length === 0 ? <EmptyAdmin message="No public-safe system checks are available." /> : data.system.map((check) => <Panel key={check.id}><div className="card-heading"><span className={`status-dot status-dot--${check.status}`} /><h2>{check.name}</h2><span className="status-label">{check.status}</span></div><strong className="system-value">{check.value}</strong><p>{check.detail}</p></Panel>)}</div>;
}
