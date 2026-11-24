import { defineConfig } from "vite";
import react from "@vitejs/plugin-react";
import tailwindcss from "@tailwindcss/vite";

// /api is proxied to FastAPI so the browser sees one origin (also needed for the microphone and WebAuthn on localhost).
export default defineConfig({
  plugins: [react(), tailwindcss()],
  server: { port: 5174, proxy: { "/api": { target: "http://localhost:8200", changeOrigin: true } } },
});
