import React from "react";
import Link from "next/link";

import { BRAND } from "@/config/brand";

const footerLinks = [
  { href: "/methodology", label: "Methodology" },
  { href: "/sources", label: "Sources" },
  { href: "/status", label: "System status" },
] as const;

export function AppFooter() {
  return (
    <footer className="app-footer">
      <div className="app-footer__inner">
        <div className="app-footer__brand">
          <strong>{BRAND.name}</strong>
          <p>{BRAND.footerDisclaimer}</p>
          <small>{BRAND.copyright}</small>
        </div>
        <nav aria-label="Footer navigation">
          <ul className="app-footer__links">
            {footerLinks.map((item) => (
              <li key={item.href}>
                <Link href={item.href}>{item.label}</Link>
              </li>
            ))}
          </ul>
        </nav>
      </div>
    </footer>
  );
}
