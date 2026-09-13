import path from "node:path";

import type { NextConfig } from "next";

const contentSecurityPolicy = [
  "default-src 'self'",
  "base-uri 'self'",
  "object-src 'none'",
  "frame-ancestors 'none'",
  "form-action 'self'",
  "script-src 'self' 'unsafe-inline'",
  "style-src 'self' 'unsafe-inline'",
  "img-src 'self' data: blob: https://images.pokemontcg.io https://tcg.pokemon.com https://poke-holo.b-cdn.net",
  "font-src 'self' data:",
  "connect-src 'self' https://*.supabase.co wss://*.supabase.co",
  "worker-src 'self' blob:",
  "manifest-src 'self'",
  "upgrade-insecure-requests",
].join("; ");

// Vercel owns the Next.js server output and file tracing for its adapter. The
// standalone bundle is only needed by deploy/Dockerfile.web on the VPS.
const nextOutputConfig: Pick<NextConfig, "output" | "outputFileTracingRoot"> =
  process.env.VERCEL === "1"
    ? {}
    : {
        output: "standalone",
        outputFileTracingRoot: path.join(__dirname, "../.."),
      };

const nextConfig: NextConfig = {
  reactStrictMode: true,
  ...nextOutputConfig,
  poweredByHeader: false,
  typedRoutes: true,
  async headers() {
    return [
      {
        source: "/:path*",
        headers: [
          { key: "Content-Security-Policy", value: contentSecurityPolicy },
          { key: "X-Content-Type-Options", value: "nosniff" },
          { key: "X-Frame-Options", value: "DENY" },
          { key: "Referrer-Policy", value: "strict-origin-when-cross-origin" },
          { key: "Permissions-Policy", value: "camera=(), microphone=(), geolocation=(), payment=(), usb=()" },
          { key: "Cross-Origin-Opener-Policy", value: "same-origin" },
          { key: "Strict-Transport-Security", value: "max-age=31536000; includeSubDomains" },
        ],
      },
      {
        source: "/landing-pages/pokemon-kage.html",
        headers: [
          { key: "Content-Security-Policy", value: contentSecurityPolicy.replace("frame-ancestors 'none'", "frame-ancestors 'self'") },
          { key: "X-Frame-Options", value: "SAMEORIGIN" },
        ],
      },
    ];
  },
};

export default nextConfig;
