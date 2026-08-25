"use client";

import Link from "next/link";
import { useEffect } from "react";

export default function GlobalError({ error, reset }: { error: Error & { digest?: string }; reset: () => void }) {
  useEffect(() => {
    console.error("Dashboard route failed", error);
  }, [error]);

  return (
    <section className="page-shell state-page" aria-labelledby="error-title">
      <span className="status-code">ERR_ROUTE</span>
      <h1 id="error-title">The route could not be rendered.</h1>
      <p>No observation data was substituted. Retry the request or return to the dashboard.</p>
      <div className="button-row">
        <button className="button" type="button" onClick={reset}>Retry</button>
        <Link className="button button--secondary" href="/">Dashboard</Link>
      </div>
    </section>
  );
}
