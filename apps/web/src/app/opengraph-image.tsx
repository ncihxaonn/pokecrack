import React from "react";
import { ImageResponse } from "next/og";

import { BRAND } from "@/config/brand";

export const alt = `${BRAND.name} observed Pokémon TCG activity dashboard`;
export const size = { width: 1200, height: 630 };
export const contentType = "image/png";

export default function OpenGraphImage() {
  return new ImageResponse(
    <div style={{ width: "100%", height: "100%", display: "flex", padding: "42px", color: "#171a21", background: "#f3f4f7", fontFamily: "sans-serif" }}>
      <div style={{ position: "relative", width: "100%", height: "100%", display: "flex", flexDirection: "column", justifyContent: "space-between", overflow: "hidden", border: "1px solid #e2e5eb", borderRadius: 34, padding: "42px 48px", background: "#ffffff", boxShadow: "0 18px 50px rgba(23,26,33,.08)" }}>
        <div style={{ position: "absolute", right: 48, top: 86, width: 390, height: 390, borderRadius: 999, background: "radial-gradient(circle, rgba(239,79,145,.28), rgba(118,87,237,.13) 38%, rgba(49,94,251,.04) 64%, transparent 70%)" }} />
        <div style={{ position: "absolute", right: 176, top: 220, width: 86, height: 86, border: "16px solid #7657ed", borderRadius: 999, background: "#ffffff", boxShadow: "0 0 0 28px rgba(118,87,237,.12)" }} />
        <div style={{ display: "flex", alignItems: "center", gap: 14, fontSize: 22, fontWeight: 800, letterSpacing: 4 }}><span style={{ display: "flex", width: 38, height: 38, alignItems: "center", justifyContent: "center", borderRadius: 12, color: "#ffffff", background: "linear-gradient(145deg,#315efb,#7657ed)" }}>P</span>{BRAND.shortName}</div>
        <div style={{ display: "flex", flexDirection: "column", maxWidth: 710 }}><span style={{ color: "#315efb", fontSize: 18, fontWeight: 750, letterSpacing: 3, textTransform: "uppercase" }}>Worldwide qualifying-hit atlas</span><span style={{ marginTop: 20, fontSize: 66, fontWeight: 760, lineHeight: 1.03, letterSpacing: -3 }}>{BRAND.tagline}</span><span style={{ marginTop: 24, color: "#667085", fontSize: 23, lineHeight: 1.4 }}>Country-level Pokémon TCG observations, visualised without predictive claims.</span></div>
        <div style={{ display: "flex", justifyContent: "space-between", color: "#87909d", fontFamily: "monospace", fontSize: 16 }}><span>UNOFFICIAL · EXPERIMENTAL · NON-COMMERCIAL</span><span>POKECRACK / ATLAS</span></div>
      </div>
    </div>,
    size,
  );
}
