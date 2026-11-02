import path from "node:path";
import tailwindcss from "@tailwindcss/vite";
import react from "@vitejs/plugin-react";
import { defineConfig } from "vitest/config";

export default defineConfig({
  plugins: [react(), tailwindcss()],
  resolve: { alias: { "@": path.resolve(__dirname, "src") } },
  server: {
    port: 5173,
    // Same-origin API in dev, so the SameSite=Strict refresh cookie just works.
    proxy: { "/api": { target: process.env.VITE_API_PROXY ?? "http://localhost:8000", changeOrigin: true } },
  },
  build: {
    rollupOptions: {
      output: {
        manualChunks: {
          react: ["react", "react-dom", "react-router-dom"],
          charts: ["recharts"],
          ui: ["@radix-ui/react-dialog", "@radix-ui/react-popover", "@radix-ui/react-select", "@radix-ui/react-dropdown-menu", "@radix-ui/react-tooltip"],
        },
      },
    },
  },
  test: { environment: "node" },
});
