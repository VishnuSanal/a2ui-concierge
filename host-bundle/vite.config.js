import { defineConfig } from "vite";

export default defineConfig({
  server: {
    allowedHosts: true,
    proxy: {
      "/chat": { target: "http://localhost:8000", changeOrigin: true },
      "/health": { target: "http://localhost:8000", changeOrigin: true },
      "/x402": { target: "http://localhost:8000", changeOrigin: true },
    },
  },
  build: {
    lib: {
      entry: "src/shim.js",
      name: "A2UIHost",
      formats: ["iife"],
      fileName: () => "a2ui-host.iife.js",
    },
    rollupOptions: { output: { inlineDynamicImports: true } },
  },
});
