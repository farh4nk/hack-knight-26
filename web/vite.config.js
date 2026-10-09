import { defineConfig } from "vite";
import react from "@vitejs/plugin-react";

export default defineConfig({
  plugins: [react()],
  server: {
    port: 5173,
    // ElevenLabs calls go through the local Express server so the API key stays server-side.
    proxy: { "/api": "http://localhost:8787" },
  },
});
