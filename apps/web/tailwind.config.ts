import type { Config } from "tailwindcss";

const config: Config = {
  content: ["./src/**/*.{ts,tsx,mdx}"],
  theme: {
    extend: {
      colors: {
        ink: "#07080c",
        panel: "#0d1017",
        line: "#242938",
        muted: "#8b93a7",
        signal: "#9d7bff",
        positive: "#35d49a",
        warning: "#f5b942",
        negative: "#ff667d",
      },
      boxShadow: {
        terminal: "0 20px 80px rgba(0, 0, 0, 0.34)",
      },
      fontFamily: {
        sans: ["Inter", "ui-sans-serif", "system-ui", "sans-serif"],
        mono: ["ui-monospace", "SFMono-Regular", "Menlo", "monospace"],
      },
    },
  },
  plugins: [],
};

export default config;
