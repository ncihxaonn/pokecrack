import React, { type ReactNode } from "react";

import { AdminShell } from "@/components/admin/admin-views";
import { requireAdmin } from "../_lib/auth";

export const dynamic = "force-dynamic";

export default async function ProtectedAdminLayout({ children }: { children: ReactNode }) {
  const access = await requireAdmin();
  return <AdminShell email={access.email} via={access.via}>{children}</AdminShell>;
}
