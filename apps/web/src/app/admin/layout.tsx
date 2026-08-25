import type { Metadata } from "next";
import type { ReactNode } from "react";

export const metadata: Metadata = {
  title: { default: "Admin", template: "%s · Admin · Pokecrack" },
  robots: { index: false, follow: false, noarchive: true, nosnippet: true },
};

export default function AdminRootLayout({ children }: { children: ReactNode }) {
  return children;
}
