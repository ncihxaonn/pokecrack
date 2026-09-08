import React from "react";

import { BRAND } from "@/config/brand";

export function AppFooter() {
  return (
    <footer className="app-footer">
      <div className="app-footer__inner">
        <div className="app-footer__brand">
          <strong>{BRAND.name}</strong>
          <p>{BRAND.footerDisclaimer}</p>
          <small>{BRAND.copyright}</small>
        </div>
      </div>
    </footer>
  );
}
