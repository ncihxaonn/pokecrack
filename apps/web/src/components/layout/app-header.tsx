import React from "react";
import Link from "next/link";

import { BRAND } from "@/config/brand";

const publicNavigation = [
  { href: "/sets", label: "Sets" },
  { href: "/regions", label: "Regions" },
  { href: "/retailers", label: "Retailers" },
  { href: "/batches", label: "Batches" },
  { href: "/methodology", label: "Methodology" },
  { href: "/sources", label: "Sources" },
  { href: "/status", label: "Status" },
] as const;

function NavigationLinks() {
  return (
    <ul className="nav-list">
      {publicNavigation.map((item) => (
        <li key={item.href}>
          <Link href={item.href}>{item.label}</Link>
        </li>
      ))}
    </ul>
  );
}

export function AppHeader() {
  return (
    <header className="app-header">
      <div className="app-header__inner">
        <Link className="wordmark" href="/" aria-label={`${BRAND.name} home`}>
          <span className="wordmark__mark" aria-hidden="true"><span /></span>
          <span>{BRAND.shortName}</span>
        </Link>
        <nav className="desktop-nav" aria-label="Primary navigation">
          <NavigationLinks />
        </nav>
        <details className="mobile-menu">
          <summary aria-label="Open navigation">Menu</summary>
          <nav aria-label="Mobile navigation">
            <NavigationLinks />
          </nav>
        </details>
      </div>
    </header>
  );
}
