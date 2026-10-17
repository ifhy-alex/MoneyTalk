import react from "@vitejs/plugin-react";
import { defineConfig } from "vite";

// En Docker el backend se llama "api"; en el host, 127.0.0.1 (evita el ::1 de Windows).
const apiTarget = process.env.VITE_API_TARGET ?? "http://127.0.0.1:8000";

export default defineConfig({
  plugins: [react()],
  server: {
    port: 5173,
    proxy: { "/api": { target: apiTarget, changeOrigin: true } },
  },
});
