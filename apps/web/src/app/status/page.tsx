import type { Metadata } from "next";
import { redirect } from "next/navigation";

export const metadata: Metadata = { robots: { index: false, follow: false } };

// Retired public section: preserve old bookmarks without rendering its contents.
export default function StatusPage() {
  redirect("/");
}
