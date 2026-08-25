import React from "react";
import { ImageResponse } from "next/og";

import { BRAND } from "@/config/brand";

export const alt = `${BRAND.name} observed Pokémon TCG activity dashboard`;
export const size = { width: 1200, height: 630 };
export const contentType = "image/png";

export default function OpenGraphImage() {
  return new ImageResponse(
    <div style={{ width: "100%", height: "100%", display: "flex", flexDirection: "column", justifyContent: "space-between", padding: "64px 72px", color: "#f0f3f6", background: "#080a0c", fontFamily: "monospace" }}>
      <div style={{ display: "flex", alignItems: "center", gap: 14, fontSize: 26, letterSpacing: 6 }}><span style={{ color: "#a6ff4d", fontSize: 42 }}>›</span>{BRAND.shortName}<span style={{ width: 13, height: 28, background: "#a6ff4d" }} /></div>
      <div style={{ display: "flex", flexDirection: "column", maxWidth: 990 }}><span style={{ color: "#a6ff4d", fontSize: 20, letterSpacing: 4, textTransform: "uppercase" }}>Australia · observed activity</span><span style={{ marginTop: 24, fontFamily: "sans-serif", fontSize: 76, fontWeight: 700, lineHeight: 1.04, letterSpacing: -4 }}>{BRAND.tagline}</span><span style={{ marginTop: 30, color: "#8d98a5", fontFamily: "sans-serif", fontSize: 25, lineHeight: 1.4 }}>{BRAND.observationDisclaimer}</span></div>
      <div style={{ display: "flex", justifyContent: "space-between", color: "#606a76", fontSize: 18 }}><span>UNOFFICIAL · EXPERIMENTAL · NON-COMMERCIAL</span><span>pokecrack / data</span></div>
    </div>,
    size,
  );
}
