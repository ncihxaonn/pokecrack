"use client";

import React, { Suspense, useRef } from "react";
import Link from "next/link";
import { usePathname } from "next/navigation";
import { Search } from "lucide-react";

import { BRAND } from "@/config/brand";

const publicNavigation = [
  { href: "/", label: "Overview" },
  { href: "/sets", label: "Sets" },
  { href: "/regions", label: "Regions" },
  { href: "/retailers", label: "Retailers" },
  { href: "/batches", label: "Batches" },
] as const;

function HeaderContent({ pathname }: { pathname: string | null }) {
  const mobileMenu = useRef<HTMLDetailsElement>(null);
  const isAdmin = pathname?.startsWith("/admin");
  const activeItem = publicNavigation.find((item) => item.href === "/" ? pathname === "/" : pathname?.startsWith(`${item.href}/`) || pathname === item.href);
  const closeMenu = () => { if (mobileMenu.current) mobileMenu.current.open = false; };
  const navigation = (
    <ul className="nav-list">
      {publicNavigation.map(({ href, label }) => (
        <li key={href}>
          <Link href={href} aria-current={activeItem?.href === href ? "page" : undefined} onClick={closeMenu}>
            {label}
          </Link>
        </li>
      ))}
    </ul>
  );
  return (
    <header className={`app-header${isAdmin ? " app-header--admin" : ""}`}>
      <div className="app-header__inner">
        <Link className="wordmark" href="/" aria-label={`${BRAND.name} home`}>
          <span className="wordmark__mark" aria-hidden="true"><span /></span>
          <span>{BRAND.name}</span>
        </Link>
        <nav className="desktop-nav" aria-label="Primary navigation">
          {navigation}
        </nav>
        <form className="header-search" action="/sets" method="get" role="search" aria-label="Find observed sets">
          <Search size={16} aria-hidden="true" />
          <input type="search" name="q" aria-label="Search observed sets" placeholder="Search sets" />
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
