import { defineConfig, loadEnv } from "vite";
import react from "@vitejs/plugin-react";
import { fileURLToPath } from "node:url";
import { apiProxyTarget } from "./vite.proxy";

export default defineConfig(({ mode }) => {
  const env = loadEnv(mode, process.cwd(), "VITE_");

  return {
    build: {
      rollupOptions: {
        output: {
          manualChunks(id) {
            if (id.includes("/node_modules/react") || id.includes("/node_modules/react-dom")) {
              return "react-vendor";
            }
            if (id.includes("/node_modules/lucide-react")) {
              return "icons";
            }
            if (id.includes("/src/lib/api")) {
              return "api-client";
            }
            return undefined;
          },
        },
      },
    },
    plugins: [react],
    resolve: {
      alias: {
        "@": fileURLToPath(new URL("./src", import.meta.url)),
      },
    },
    server: {
      port: 5173,
      proxy: {
        "/api": {
          target: apiProxyTarget(env),
          changeOrigin: true,
        },
      },
    },
  };
});
