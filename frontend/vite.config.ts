import { defineConfig, loadEnv } from "vite";
import { svelte } from "@sveltejs/vite-plugin-svelte";
import path from "path";

// https://vite.dev/config/
export default defineConfig(({ mode }) => {
  const env = loadEnv(mode, process.cwd(), "");
  const backendTarget =
    env.VITE_DEV_BACKEND_URL || env.VITE_BACKEND_URL || "http://127.0.0.1:7409";
  const wsTarget = backendTarget.replace(/^http/, "ws");

  return {
    plugins: [svelte()],
    resolve: {
      alias: {
        $lib: path.resolve("./src/lib"),
      },
    },
    server: {
      proxy: {
        "/api": {
          target: backendTarget,
          changeOrigin: true,
        },
        "/ws": {
          target: wsTarget,
          changeOrigin: true,
          ws: true,
        },
      },
    },
  };
});
