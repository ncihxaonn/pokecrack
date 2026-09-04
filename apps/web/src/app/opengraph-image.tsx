import React from "react";
import { ImageResponse } from "next/og";

import { BRAND } from "@/config/brand";

export const alt = `${BRAND.name} observed Pokémon TCG activity dashboard`;
export const size = { width: 1200, height: 630 };
export const contentType = "image/png";

export default function OpenGraphImage() {
  return new ImageResponse(
    <div style={{ width: "100%", height: "100%", display: "flex", padding: "42px", color: "#101512", background: "#f2f6f3", fontFamily: "sans-serif" }}>
      <div style={{ position: "relative", width: "100%", height: "100%", display: "flex", flexDirection: "column", justifyContent: "space-between", overflow: "hidden", border: "1px solid #cad4cc", borderRadius: 34, padding: "42px 48px", background: "#ffffff", boxShadow: "0 18px 50px rgba(16,21,18,.07)" }}>
        <div style={{ position: "absolute", right: 48, top: 86, width: 390, height: 390, borderRadius: 999, background: "#e7f2eb" }} />
        <div style={{ position: "absolute", right: 176, top: 220, width: 86, height: 86, border: "16px solid #0d7444", borderRadius: 999, background: "#ffffff", boxShadow: "0 0 0 28px rgba(13,116,68,.12)" }} />
        <div style={{ display: "flex", alignItems: "center", gap: 14, fontSize: 22, fontWeight: 800, letterSpacing: 4 }}><span style={{ display: "flex", width: 38, height: 38, alignItems: "center", justifyContent: "center", borderRadius: 12, color: "#ffffff", background: "#101512" }}>P</span>{BRAND.shortName}</div>
        <div style={{ display: "flex", flexDirection: "column", maxWidth: 710 }}><span style={{ color: "#0d7444", fontSize: 18, fontWeight: 750, letterSpacing: 3, textTransform: "uppercase" }}>Worldwide qualifying-hit atlas</span><span style={{ marginTop: 20, fontSize: 66, fontWeight: 760, lineHeight: 1.03, letterSpacing: -3 }}>{BRAND.tagline}</span><span style={{ marginTop: 24, color: "#5e6962", fontSize: 23, lineHeight: 1.4 }}>Country and product-market Pokémon TCG coverage buckets, visualised without predictive claims.</span></div>
        <div style={{ display: "flex", justifyContent: "space-between", color: "#78827b", fontFamily: "monospace", fontSize: 16 }}><span>UNOFFICIAL · EXPERIMENTAL · NON-COMMERCIAL</span><span>POKECRACK / ATLAS</span></div>
      </div>
    </div>,
    size,
  );
}
