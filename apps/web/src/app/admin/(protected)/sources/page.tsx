import React from "react";
import type { Metadata } from "next";
import { AdminHeading, AdminModeNotice, AdminSourcesView } from "@/components/admin/admin-views";
import { getAdminSnapshot } from "../../_lib/admin-data";
import { requireAdmin } from "../../_lib/auth";
export const metadata: Metadata = { title: "Sources" };
export default async function AdminSourcesPage() { const access = await requireAdmin(); const snapshot = await getAdminSnapshot(access); return <><AdminHeading title="Source policies" description="Allowlist posture and intentionally disabled mutation controls." /><AdminModeNotice message={snapshot.message} synthetic={snapshot.synthetic} /><AdminSourcesView available={snapshot.status === "ready"} /></>; }
