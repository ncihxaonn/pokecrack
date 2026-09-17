import React, { type ReactNode } from "react";
import { ComingSoon } from "../_components/coming-soon";

export default function RegionsLayout({ children }: { children: ReactNode }) {
  return <ComingSoon>{children}</ComingSoon>;
}
