import React from "react";
import type { Metadata } from "next";
import { AdminBrowserView, AdminHeading, AdminModeNotice } from "@/components/admin/admin-views";
import { getAdminSnapshot } from "../../_lib/admin-data";
import { requireAdmin } from "../../_lib/auth";
export const metadata: Metadata = { title: "Browser" };
export default async function AdminBrowserPage() { const access = await requireAdmin(); const snapshot = await getAdminSnapshot(access); return <><AdminHeading title="Browser sessions" description="Opaque profile health only; never browser cookies, tokens or remote-control secrets." /><AdminModeNotice message={snapshot.message} status={snapshot.status} synthetic={snapshot.synthetic} /><AdminBrowserView data={snapshot.status === "ready" ? snapshot.data : null} /></>; }
