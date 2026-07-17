import { defineConfig } from "vite";
import react from "@vitejs/plugin-react";
import { VitePWA } from "vite-plugin-pwa";

// En desarrollo, las llamadas a /api se redirigen al backend local (docker dev).
export default defineConfig({
  plugins: [
    react(),
    VitePWA({
      registerType: "autoUpdate",
      includeAssets: ["favicon.svg"],
      manifest: {
        name: "Verificación ISH y SDC",
        short_name: "ISH/SDC",
        description: "Verificación Periódica de ISH y SDC — PDVSA",
        theme_color: "#0b5cad",
        background_color: "#ffffff",
        display: "standalone",
        start_url: "/",
        icons: [
          { src: "icon-192.png", sizes: "192x192", type: "image/png" },
          { src: "icon-512.png", sizes: "512x512", type: "image/png" },
          { src: "icon-512.png", sizes: "512x512", type: "image/png", purpose: "maskable" },
        ],
      },
      workbox: {
        // No cachear la API: los datos van por IndexedDB + sync explícito.
        navigateFallbackDenylist: [/^\/api/, /^\/verificar/, /^\/reports/],
      },
    }),
  ],
  server: {
    proxy: {
      "/api": { target: "http://localhost:8010", changeOrigin: true },
    },
  },
});
