"use client";

import React, { Suspense, useRef } from "react";
import Link from "next/link";
import { usePathname } from "next/navigation";
import { Boxes, Database, Globe2, LayoutDashboard, Search, Store } from "lucide-react";

import { BRAND } from "@/config/brand";

const publicNavigation = [
  { href: "/", label: "Overview", icon: LayoutDashboard },
  { href: "/sets", label: "Sets", icon: Boxes },
  { href: "/regions", label: "Regions", icon: Globe2 },
  { href: "/retailers", label: "Retailers", icon: Store },
  { href: "/batches", label: "Batches", icon: Database },
] as const;

function HeaderContent({ pathname }: { pathname: string | null }) {
  const mobileMenu = useRef<HTMLDetailsElement>(null);
  const isAdmin = pathname?.startsWith("/admin");
  const activeItem = publicNavigation.find((item) => item.href === "/" ? pathname === "/" : pathname?.startsWith(`${item.href}/`) || pathname === item.href);
  const closeMenu = () => { if (mobileMenu.current) mobileMenu.current.open = false; };
  const navigation = (
    <ul className="nav-list">
      {publicNavigation.map(({ href, label, icon: Icon }) => (
        <li key={href}>
          <Link href={href} aria-current={activeItem?.href === href ? "page" : undefined} onClick={closeMenu}>
            <Icon size={17} aria-hidden="true" />{label}
          </Link>
        </li>
      ))}
    </ul>
  );
  return (
    <header className={`app-header${isAdmin ? " app-header--admin" : ""}`}>
      <div className="app-sidebar">
        <Link className="wordmark" href="/" aria-label={`${BRAND.name} home`}>
          <span className="wordmark__mark" aria-hidden="true"><span /></span>
          <span>{BRAND.shortName}<small>Opening evidence</small></span>
        </Link>
        <nav className="desktop-nav" aria-label="Primary navigation">
          <span className="nav-caption">Workspace</span>
          {navigation}
        </nav>
      </div>
      <div className="app-header__inner">
        <span className="workspace-label">PokeCrack <span aria-hidden="true">/</span> <strong>{isAdmin ? "Administration" : activeItem?.label ?? "Workspace"}</strong></span>
        <form className="header-search" action="/sets" method="get" role="search" aria-label="Find observed sets">
          <Search size={16} aria-hidden="true" />
          <input type="search" name="q" aria-label="Search observed sets" placeholder="Search observed sets…" />
        </form>
        <details className="mobile-menu" ref={mobileMenu}>
          <summary aria-label="Toggle navigation">Menu</summary>
          <nav aria-label="Mobile navigation">{navigation}</nav>
        </details>
      </div>
    </header>
  );
}

function ConnectedHeader() {
  return <HeaderContent pathname={usePathname()} />;
}

export function AppHeader() {
  return <Suspense fallback={<HeaderContent pathname={null} />}><ConnectedHeader /></Suspense>;
}
