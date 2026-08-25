import React from "react";
import type { Metadata } from "next";
import { AdminHeading, AdminJobsView, AdminModeNotice } from "@/components/admin/admin-views";
import { getAdminSnapshot } from "../../_lib/admin-data";
import { requireAdmin } from "../../_lib/auth";
export const metadata: Metadata = { title: "Jobs" };
export default async function AdminJobsPage() { const access = await requireAdmin(); const snapshot = await getAdminSnapshot(access); return <><AdminHeading title="Collection jobs" description="Bounded scheduler summaries; unsafe run controls stay disabled." /><AdminModeNotice message={snapshot.message} synthetic={snapshot.synthetic} /><AdminJobsView data={snapshot.status === "ready" ? snapshot.data : null} /></>; }
