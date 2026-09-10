import js from "@eslint/js";
import { defineConfig, globalIgnores } from "eslint/config";
import nextCoreWebVitals from "eslint-config-next/core-web-vitals";
import nextTypeScript from "eslint-config-next/typescript";

export default defineConfig([
  globalIgnores([".next/**", "coverage/**", "next-env.d.ts", "public/landing-pages/secret-pathways-assets/**", "public/landing-pages/pokemon-models/loader.js"]),
  js.configs.recommended,
  ...nextCoreWebVitals,
  ...nextTypeScript,
]);
