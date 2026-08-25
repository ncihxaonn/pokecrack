import React from "react";
import type { Metadata } from "next";

import { AdminHeading, AdminModeNotice, AdminOverview } from "@/components/admin/admin-views";
import { requireAdmin } from "../_lib/auth";
import { getAdminSnapshot } from "../_lib/admin-data";

export const metadata: Metadata = { title: "Overview" };
export default async function AdminPage() { const access = await requireAdmin(); const snapshot = await getAdminSnapshot(access); return <><AdminHeading title="Operations overview" description="Read-only, public-safe summaries for the private control plane." /><AdminModeNotice message={snapshot.message} synthetic={snapshot.synthetic} /><AdminOverview snapshot={snapshot} /></>; }
