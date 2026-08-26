import React, { type ReactNode } from "react";
import Link from "next/link";

import type { AdminStatusData, OperationalState } from "@/app/admin/_lib/admin-fixture";
import { Panel, TableFrame } from "@/components/ui/dashboard-ui";
import { BRAND } from "@/config/brand";
import { formatCompactNumber, formatDate } from "@/lib/format";

const adminNavigation = [
  { href: "/admin", label: "Overview" },
  { href: "/admin/sources", label: "Sources" },
  { href: "/admin/jobs", label: "Jobs" },
  { href: "/admin/browser", label: "Browser" },
  { href: "/admin/ai-usage", label: "AI usage" },
  { href: "/admin/system", label: "System" },
] as const;

function OperationalBadge({ state }: { state: OperationalState }) {
  return (
    <span className={`admin-state admin-state--${state}`}>
      <span className={`status-dot status-dot--${state}`} aria-hidden="true" />
      {state}
    </span>
  );
}

export function AdminShell({ email, via, children }: { email: string; via: "supabase"; children: ReactNode }) {
  return (
    <div className="admin-shell">
      <aside className="admin-sidebar">
        <div className="admin-sidebar__identity">
          <span className="eyebrow">Control plane</span>
          <strong>{BRAND.shortName} / ADMIN</strong>
          <small>{email}</small>
          <span className={`admin-session admin-session--${via}`}>Verified Supabase user</span>
        </div>
        <nav aria-label="Admin navigation">
          <ul>{adminNavigation.map((item) => <li key={item.href}><Link href={item.href}>{item.label}</Link></li>)}</ul>
        </nav>
        <p>Operational summaries are read-only unless a policy-validating, audited server endpoint is explicitly connected.</p>
      </aside>
      <main className="admin-content">{children}</main>
    </div>
  );
}

export function AdminHeading({ title, description }: { title: string; description: string }) {
  return <header className="admin-heading"><span className="eyebrow">Restricted · noindex</span><h1>{title}</h1><p>{description}</p></header>;
}

export function AdminModeNotice({ message, status, synthetic }: { message: string; status: "ready" | "unavailable"; synthetic: boolean }) {
  const mode = status === "unavailable" ? "unavailable" : synthetic ? "demo" : "live";
  const label = status === "unavailable" ? "UNAVAILABLE / FAIL CLOSED" : synthetic ? "SYNTHETIC / READ ONLY" : "LIVE / READ ONLY";
  return <aside className={`admin-mode admin-mode--${mode}`} role="status"><strong>{label}</strong><p>{message}</p></aside>;
}

export function DisabledMutation({ label, reason }: { label: string; reason: string }) {
  return <div className="disabled-action"><button className="button button--secondary" type="button" disabled>{label}</button><small>{reason}</small></div>;
}

function EmptyAdmin({ message }: { message: string }) {
  return <Panel><p className="empty-cell">{message}</p></Panel>;
}

export function AdminOverview({ snapshot }: { snapshot: { status: "ready"; data: AdminStatusData } | { status: "unavailable" } }) {
  if (snapshot.status === "unavailable") return <EmptyAdmin message="No operational counts are available." />;
  const workerAttention = snapshot.data.workers.filter((worker) => worker.state !== "healthy").length;
  return (
    <>
      <div className="admin-kpis">
        <Panel><span>Queue</span><strong>{formatCompactNumber(snapshot.data.queue.queued)}</strong><small>{snapshot.data.queue.running} running · {snapshot.data.queue.dead} dead</small></Panel>
        <Panel><span>Pipeline accepted</span><strong>{formatCompactNumber(snapshot.data.pipeline.accepted)}</strong><small>{snapshot.data.pipeline.rejected} rejected · {snapshot.data.pipeline.activityOnly} activity only</small></Panel>
        <Panel><span>Worker attention</span><strong>{workerAttention}</strong><small>{snapshot.data.workers.length} workers · {snapshot.data.pipeline.freshness}</small></Panel>
        <Panel><span>AI budget</span><strong>${snapshot.data.ai.estimatedCostAud.toFixed(2)}</strong><small>{snapshot.data.ai.budgetAud === null ? "budget not reported" : `of $${snapshot.data.ai.budgetAud.toFixed(2)} AUD`}</small></Panel>
      </div>
      <div className="admin-grid">
        <Panel>
          <h2>Worker heartbeat</h2>
          <ul className="admin-status-list">{snapshot.data.workers.map((worker) => <li key={worker.id}><div><strong>{worker.label}</strong><small>{worker.currentWork} · {worker.heartbeat}</small></div><OperationalBadge state={worker.state} /></li>)}</ul>
        </Panel>
        <Panel>
          <h2>Recent decisions</h2>
          <ul className="admin-status-list">{snapshot.data.records.map((record) => <li key={record.id}><div><strong>{record.label}</strong><small>{record.freshness}</small></div><span className={`admin-decision admin-decision--${record.decision}`}>{record.decision}</span></li>)}</ul>
        </Panel>
      </div>
    </>
  );
}

export function AdminSourcesView({ data }: { data: AdminStatusData | null }) {
  if (!data) return <EmptyAdmin message="Live source-policy status is unavailable; no synthetic registry was substituted." />;
  return (
    <>
      <div className="admin-grid">
        <Panel>
          <h2>Source policy registry</h2>
          <TableFrame label="Source policy registry">
            <table><thead><tr><th>Source</th><th>Policy</th><th>Adapter</th><th>Freshness</th></tr></thead><tbody>{data.sources.map((source) => <tr key={source.id}><td><strong>{source.label}</strong><small><code>{source.id}</code></small></td><td>{source.policy}</td><td><OperationalBadge state={source.adapterStatus} /></td><td>{source.freshness}</td></tr>)}</tbody></table>
          </TableFrame>
          <DisabledMutation label="Add source" reason="Disabled: requires source-policy validation and an append-only audit write." />
        </Panel>
        <Panel>
          <h2>Adapter posture</h2>
          <ul className="admin-status-list">{data.adapters.map((adapter) => <li key={adapter.id}><div><strong>{adapter.label}</strong><small>{adapter.mode} · {adapter.freshness}</small></div><OperationalBadge state={adapter.status} /></li>)}</ul>
        </Panel>
      </div>
      <Panel className="admin-policy-panel"><h2>Required enablement record</h2><ul className="admin-checklist"><li>Exact domain and enabled route</li><li>Terms, robots and authentication basis</li><li>Rate, concurrency, page and retention bounds</li><li>Statistics-eligibility default and kill switch</li><li>Named owner, review date and adapter fixture</li></ul></Panel>
    </>
  );
}

export function AdminJobsView({ data }: { data: AdminStatusData | null }) {
  if (!data) return <EmptyAdmin message="Job status is unavailable." />;
  return <Panel><TableFrame label="Admin jobs"><table><thead><tr><th>Job</th><th>Status</th><th>Attempts</th><th>Freshness</th><th>Records</th><th>Action</th></tr></thead><tbody>{data.jobs.length === 0 ? <tr><td colSpan={6} className="empty-cell">No jobs are available.</td></tr> : data.jobs.map((job) => <tr key={job.id}><td><strong>{job.label}</strong><small><code>{job.id}</code></small></td><td><span className={`admin-decision admin-decision--${job.status}`}>{job.status}</span></td><td>{job.attempts}</td><td>{job.freshness}</td><td>{formatCompactNumber(job.records)}</td><td><button type="button" disabled>Run disabled</button></td></tr>)}</tbody></table></TableFrame><p className="admin-footnote">Job mutations are disabled because this web shell has no policy-validating, audited queue endpoint.</p></Panel>;
}

export function AdminBrowserView({ data }: { data: AdminStatusData | null }) {
  if (!data) return <EmptyAdmin message="Browser-session status is unavailable." />;
  return <div className="admin-grid">{data.browserSessions.length === 0 ? <EmptyAdmin message="No browser-session summaries are available." /> : data.browserSessions.map((session) => <Panel key={session.id}><div className="card-heading"><OperationalBadge state={session.browser} /><h2>{session.label}</h2></div><dl className="definition-list"><div><dt>Browser</dt><dd>{session.browser}</dd></div><div><dt>Extension</dt><dd>{session.extension}</dd></div><div><dt>Login</dt><dd>{session.login}</dd></div><div><dt>Freshness</dt><dd>{session.freshness}</dd></div></dl><DisabledMutation label="Open session" reason="Disabled: operator action belongs on the loopback-only VPS console." /></Panel>)}</div>;
}

export function AdminAiUsageView({ data }: { data: AdminStatusData | null }) {
  if (!data) return <EmptyAdmin message="AI usage ledger is unavailable." />;
  const reportedBudget = data.ai.budgetAud === null ? null : `$${data.ai.budgetAud.toFixed(2)}`;
  return <><div className="admin-kpis admin-kpis--compact"><Panel><span>Requests</span><strong>{formatCompactNumber(data.ai.requests)}</strong></Panel><Panel><span>Input tokens</span><strong>{formatCompactNumber(data.ai.inputTokens)}</strong></Panel><Panel><span>Output tokens</span><strong>{formatCompactNumber(data.ai.outputTokens)}</strong></Panel><Panel><span>Estimated / budget</span><strong>${data.ai.estimatedCostAud.toFixed(2)}{reportedBudget ? ` / ${reportedBudget}` : ""}</strong><small>{reportedBudget === null ? "budget not reported" : data.ai.paused ? "AI work paused" : "within configured budget"}</small></Panel></div><Panel><TableFrame label="AI usage ledger"><table><thead><tr><th>Day</th><th>Stage</th><th>Requests</th><th>Input tokens</th><th>Output tokens</th><th>Estimated AUD</th></tr></thead><tbody>{data.ai.rows.length === 0 ? <tr><td colSpan={6} className="empty-cell">No AI usage rows are available.</td></tr> : data.ai.rows.map((row) => <tr key={`${row.day}-${row.stage}`}><td>{formatDate(row.day)}</td><td>{row.stage}</td><td>{formatCompactNumber(row.requests)}</td><td>{formatCompactNumber(row.inputTokens)}</td><td>{formatCompactNumber(row.outputTokens)}</td><td>${row.estimatedCostAud.toFixed(2)}</td></tr>)}</tbody></table></TableFrame><p className="admin-footnote">Displayed costs are snapshot estimates, not provider billing telemetry.</p></Panel></>;
}

export function AdminSystemView({ data }: { data: AdminStatusData | null }) {
  if (!data) return <EmptyAdmin message="System summary is unavailable." />;
  const capacity = [["Database", data.capacity.database], ["Storage", data.capacity.storage]] as const;
  const checkpoints = [["Backup checkpoint", data.backup], ["Aggregation checkpoint", data.aggregation]] as const;
  return <><div className="admin-grid">{capacity.map(([label, item]) => <Panel key={label}><div className="card-heading"><h2>{label}</h2><OperationalBadge state={item.status} /></div><strong className="system-value">{item.used} / {item.limit}</strong><meter min={0} max={100} value={item.usedPercent}>{item.usedPercent}%</meter><small>{item.usedPercent}% used · attention threshold {item.thresholdPercent}%</small></Panel>)}{checkpoints.map(([label, item]) => <Panel key={label}><div className="card-heading"><h2>{label}</h2><OperationalBadge state={item.status} /></div><strong className="system-value">{item.freshness}</strong><p>{item.detail}</p></Panel>)}</div><Panel className="admin-policy-panel"><h2>Service freshness</h2><ul className="admin-status-list">{data.services.map((service) => <li key={service.id}><div><strong>{service.label}</strong><small>{service.freshness}</small></div><OperationalBadge state={service.status} /></li>)}</ul></Panel></>;
}
