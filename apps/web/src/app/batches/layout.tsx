import React, { type ReactNode } from "react";
import { ComingSoon } from "../_components/coming-soon";

export default function BatchesLayout({ children }: { children: ReactNode }) {
  return <ComingSoon>{children}</ComingSoon>;
}
