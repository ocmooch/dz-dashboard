/// <reference types="vitest/config" />
import { fileURLToPath, URL } from "node:url";

import react from "@vitejs/plugin-react";
import { defineConfig } from "vite";

// The SPA is pure presentation; in dev it proxies API calls to the BFF on 8800
// so the browser only ever talks to one origin (no CORS in dev).
const BFF = "http://127.0.0.1:8800";

export default defineConfig({
  plugins: [react()],
  resolve: {
    alias: { "@": fileURLToPath(new URL("./src", import.meta.url)) },
  },
  server: {
    port: 5173,
    proxy: {
      "/v1": BFF,
      "/health": BFF,
      "/openapi.json": BFF,
    },
  },
  test: {
    environment: "jsdom",
    globals: true,
    setupFiles: "./src/test/setup.ts",
    css: false,
    coverage: {
      provider: "v8",
      include: ["src/design-system/**", "src/charts/**", "src/lib/format.ts"],
    },
  },
});
