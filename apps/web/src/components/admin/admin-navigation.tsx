"use client";

import React, { Suspense } from "react";
import Link from "next/link";
import { usePathname } from "next/navigation";

const navigation = [
  { href: "/admin", label: "Overview" },
  { href: "/admin/sources", label: "Sources" },
  { href: "/admin/jobs", label: "Jobs" },
  { href: "/admin/browser", label: "Browser" },
  { href: "/admin/ai-usage", label: "AI usage" },
  { href: "/admin/system", label: "System" },
] as const;

function Links({ pathname }: { pathname: string | null }) {
  return <ul>{navigation.map((item) => <li key={item.href}><Link href={item.href} aria-current={pathname === item.href ? "page" : undefined}>{item.label}</Link></li>)}</ul>;
}

function CurrentLinks() {
  return <Links pathname={usePathname()} />;
}

export function AdminNavigation() {
  return <nav aria-label="Admin navigation"><Suspense fallback={<Links pathname={null} />}><CurrentLinks /></Suspense></nav>;
}
