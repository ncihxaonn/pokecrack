import React from "react";
import type { Metadata } from "next";
import { AdminHeading, AdminModeNotice, AdminSystemView } from "@/components/admin/admin-views";
import { getAdminSnapshot } from "../../_lib/admin-data";
import { requireAdmin } from "../../_lib/auth";
export const metadata: Metadata = { title: "System" };
export default async function AdminSystemPage() { const access = await requireAdmin(); const snapshot = await getAdminSnapshot(access); return <><AdminHeading title="System summary" description="Bounded health indicators without credentials, internal addresses or private payloads." /><AdminModeNotice message={snapshot.message} synthetic={snapshot.synthetic} /><AdminSystemView data={snapshot.status === "ready" ? snapshot.data : null} /></>; }
