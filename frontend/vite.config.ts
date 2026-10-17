import react from "@vitejs/plugin-react";
import { defineConfig } from "vite";

// En Docker el backend se llama "api"; en el host, 127.0.0.1 (evita el ::1 de Windows).
const apiTarget = process.env.VITE_API_TARGET ?? "http://127.0.0.1:8000";

export default defineConfig({
  plugins: [react()],
  server: {
    port: 5173,
    // En Docker sobre Windows los cambios de archivos no generan eventos: usar sondeo.
    watch: process.env.VITE_POLLING === "1" ? { usePolling: true, interval: 300 } : undefined,
    proxy: { "/api": { target: apiTarget, changeOrigin: true } },
  },
});
