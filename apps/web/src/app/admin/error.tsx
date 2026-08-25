"use client";

import React from "react";

export default function AdminError({ error, reset }: { error: Error & { digest?: string; status?: number; code?: string }; reset: () => void }) {
  const forbidden = error.status === 403 || error.code === "ADMIN_FORBIDDEN" || error.message.startsWith("ADMIN_FORBIDDEN");
  return <section className="page-shell state-page"><span className="status-code">{forbidden ? "403_FORBIDDEN" : "ADMIN_ERROR"}</span><h1>{forbidden ? "This account is not allowlisted." : "The admin route could not be rendered."}</h1><p>{forbidden ? "Authentication succeeded, but this account has no administrator access." : "No operational mutation was attempted."}</p><button className="button" type="button" onClick={reset}>Retry</button></section>;
}
