import React, { type ReactNode } from "react";
import Link from "next/link";

import styles from "./coming-soon.module.css";

// A temporary presentation layer, not an authorization or data-access boundary.
// Keep the original pages intact so each section can be reopened independently.
export function ComingSoon({ children }: { children: ReactNode }) {
  return (
    <section className={styles.shell} aria-labelledby="coming-soon-title">
      <div className={styles.preview} inert aria-hidden="true">
        {children}
      </div>
      <div className={styles.overlay}>
        <div className={styles.message}>
          <h1 id="coming-soon-title">Coming soon</h1>
          <p>In the meantime, explore the Overview.</p>
          <Link className="button" href="/">Back to Overview</Link>
        </div>
      </div>
    </section>
  );
}
