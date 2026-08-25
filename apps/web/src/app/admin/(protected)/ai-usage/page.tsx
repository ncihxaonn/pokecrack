import React from "react";
import type { Metadata } from "next";
import { AdminAiUsageView, AdminHeading, AdminModeNotice } from "@/components/admin/admin-views";
import { getAdminSnapshot } from "../../_lib/admin-data";
import { requireAdmin } from "../../_lib/auth";
export const metadata: Metadata = { title: "AI usage" };
export default async function AdminAiUsagePage() { const access = await requireAdmin(); const snapshot = await getAdminSnapshot(access); return <><AdminHeading title="AI usage ledger" description="Request, token and estimated-cost summaries without prompts or model output." /><AdminModeNotice message={snapshot.message} synthetic={snapshot.synthetic} /><AdminAiUsageView data={snapshot.status === "ready" ? snapshot.data : null} /></>; }
