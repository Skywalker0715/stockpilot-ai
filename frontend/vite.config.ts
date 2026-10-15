import { defineConfig } from "vite";
import react from "@vitejs/plugin-react";

// Dev server runs on 5173 (the only origin allowed by backend CORS).
// /api is proxied to the FastAPI backend so the browser stays same-origin.
export default defineConfig({
  plugins: [react()],
  server: {
    port: 5173,
    strictPort: true,
    proxy: {
      "/api": {
        target: "http://127.0.0.1:8000",
        changeOrigin: false,
      },
    },
  },
});
