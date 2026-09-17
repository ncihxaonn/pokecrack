import React, { type ReactNode } from "react";
import { ComingSoon } from "../_components/coming-soon";

export default function RetailersLayout({ children }: { children: ReactNode }) {
  return <ComingSoon>{children}</ComingSoon>;
}
