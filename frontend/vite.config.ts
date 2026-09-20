/// <reference types="vitest/config" />
import { fileURLToPath, URL } from "node:url";

import tailwindcss from "@tailwindcss/vite";
import react from "@vitejs/plugin-react";
import { defineConfig } from "vite";

// The app serves the SPA from inside the Python package, so the build writes there rather than to dist/.
// f1telemetry/web/ is gitignored: it is a build output, not a source.
const WEB_DIR = fileURLToPath(new URL("../f1telemetry/web", import.meta.url));

export default defineConfig({
  plugins: [react(), tailwindcss()],
  resolve: {
    alias: { "@": fileURLToPath(new URL("./src", import.meta.url)) },
  },
  // In development the API is a separate origin (see DEV_ORIGINS in app.py), so 5173 is not negotiable.
  server: { port: 5173, strictPort: true },
  build: {
    outDir: WEB_DIR,
    emptyOutDir: true,
    // Fail the build rather than ship a dashboard that stutters; the live view is the whole product.
    chunkSizeWarningLimit: 600,
  },
  test: {
    environment: "jsdom",
    setupFiles: ["./src/test/setup.ts"],
    css: true,
    restoreMocks: true,
  },
});
